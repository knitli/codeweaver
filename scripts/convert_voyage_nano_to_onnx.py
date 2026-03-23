# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Convert voyage-4-nano to ONNX format for FastEmbed usage.

This script converts the VoyageAI voyage-4-nano model to ONNX format,
validates the conversion by comparing embeddings, and optionally uploads
to HuggingFace.

Requirements:
    just run it. Dependencies will autoresolve.

Usage:
    # Basic conversion
    python scripts/convert_voyage_nano_to_onnx.py

    # Validate existing ONNX model only (skip conversion)
    python scripts/convert_voyage_nano_to_onnx.py --validate-only

    # With upload to HuggingFace
    python scripts/convert_voyage_nano_to_onnx.py --upload --hf-repo knitli/voyage-4-nano-onnx

    # Custom output directory
    python scripts/convert_voyage_nano_to_onnx.py --output-dir ./models/voyage-nano-onnx
"""

import argparse
import logging
import sys

from pathlib import Path
from typing import cast

import numpy as np
import torch

from transformers import AutoModel


logger = logging.getLogger(__name__)


def convert_to_onnx(model_id: str, output_dir: Path) -> bool:
    """Convert model to ONNX format.

    Args:
        model_id: HuggingFace model ID
        output_dir: Output directory for ONNX model

    Returns:
        True if conversion successful
    """
    print(f"\n📦 Converting {model_id} to ONNX...")
    try:
        return _convert_model_and_tokenizer(model_id, output_dir)
    except Exception as e:
        logger.warning("❌ Conversion failed", exc_info=e)
        return False


def mean_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_states.size()).float()
    sum_embeddings = torch.sum(last_hidden_states * input_mask_expanded, 1)
    sum_mask = input_mask_expanded.sum(1)
    sum_mask = torch.clamp(sum_mask, min=1e-09)
    return sum_embeddings / sum_mask


def _convert_model_and_tokenizer(model_id, output_dir):
    from optimum.exporters.onnx import export
    from optimum.exporters.tasks import TasksManager
    from transformers import BertConfig

    device = "cuda"
    model = AutoModel.from_pretrained(
        model_id, trust_remote_code=True, attn_implementation="eager", dtype=torch.bfloat16
    ).to(device)
    bert_config_constructor = TasksManager.get_exporter_config_constructor(
        "onnx", library_name="transformers", model_type="qwen3", task="text-classification"
    )
    onnx_config = bert_config_constructor(BertConfig())
    export(model=model, config=onnx_config, output=output_dir)


def validate_conversion(
    original_model_id: str, onnx_model_dir: Path, test_texts: list[str] | None = None
) -> bool:  # sourcery skip: low-code-quality
    """Validate ONNX conversion by comparing embeddings.

    Args:
        original_model_id: HuggingFace model ID of original
        onnx_model_dir: Path to converted ONNX model
        test_texts: Test sentences (uses defaults if None)

    Returns:
        True if validation successful
    """
    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer

    if test_texts is None:
        test_texts = [
            "def calculate_embeddings(text: str) -> list[float]:",
            "class VectorStore: pass",
            "This is a semantic search test.",
        ]
    print("\n🔍 Validating conversion...")
    try:
        print("  - Loading original model...")
        original_model = SentenceTransformer(
            original_model_id,
            device="cuda",
            trust_remote_code=True,
            truncate_dim=1024,
            model_kwargs={"dtype": torch.bfloat16},
        )
        print(f"  - Model modules: {[type(m).__name__ for m in original_model]}")
        if hasattr(original_model, "_modules"):
            for name, module in original_model._modules.items():
                print(f"    Module {name}: {type(module).__name__}")
        print("  - Loading ONNX model...")
        onnx_model = ORTModelForFeatureExtraction.from_pretrained(
            onnx_model_dir, providers=["CUDAExecutionProvider"]
        )
        tokenizer = AutoTokenizer.from_pretrained(
            onnx_model_dir, use_fast=True, fix_mistral_regex=True
        )
        print(f"  - ONNX model inputs: {onnx_model.input_names}")
        print(f"  - ONNX model outputs: {onnx_model.output_names}")
        print("  - Comparing embeddings...")
        for i, text in enumerate(test_texts, 1):
            print(f"  - Processing text {i}...")
            orig_emb = original_model.encode([text], normalize_embeddings=True)[0]
            print(f"    Original embedding shape: {orig_emb.shape}")
            with torch.no_grad():
                features = original_model.tokenize([text])
                features = {k: v.to("cuda") for k, v in features.items()}
                if (module := original_model._first_module()) and isinstance(
                    module, torch.nn.Model
                ):
                    raw_output = cast(torch.nn.Model, module).auto_model(**features)
                    print(
                        f"    Original raw hidden states shape: {raw_output.last_hidden_state.shape}"
                    )
                print(f"    Model has {len(original_model)} modules")
                for idx, module in enumerate(original_model):
                    print(f"      Module {idx}: {type(module).__name__}")
                    if hasattr(module, "get_config_dict"):
                        print(f"        Config: {cast(torch.nn.Model, module).get_config_dict()}")
            if not tokenizer or not callable(tokenizer):
                logger.warning("Tokenizer not found for ONNX model. Skipping validation.")
                return False
            inputs = tokenizer(
                text, padding=True, truncation=True, return_tensors="pt", max_length=32768
            )  # ty:ignore[call-non-callable]
            print(f"    Tokenizer outputs: {list(inputs.keys())}")
            print(f"    Tokenized input_ids shape: {inputs['input_ids'].shape}")
            for input_name in onnx_model.input_names:
                if input_name not in inputs:
                    print(f"    ⚠️  Missing input: {input_name}, creating it...")
                    if input_name == "position_ids":
                        seq_length = inputs["input_ids"].shape[1]
                        inputs["position_ids"] = torch.arange(
                            seq_length, dtype=torch.long
                        ).unsqueeze(0)
                        print(
                            f"    Created position_ids with shape: {inputs['position_ids'].shape}"
                        )
                elif inputs[input_name] is None:
                    print(f"    ⚠️  Input is None: {input_name}")
            if hasattr(onnx_model, "device"):
                inputs = {
                    k: v.to(onnx_model.device) if hasattr(v, "to") else v for k, v in inputs.items()
                }
            print("    Running ONNX inference...")
            outputs = onnx_model(**inputs)
            print("    ONNX inference completed")
            print(f"    Debug - Output type: {type(outputs)}")
            print(f"    Debug - Has last_hidden_state: {hasattr(outputs, 'last_hidden_state')}")
            if hasattr(outputs, "last_hidden_state"):
                print(f"    Debug - last_hidden_state is None: {outputs.last_hidden_state is None}")
            if hasattr(outputs, "__dict__"):
                print(f"    Debug - Output attributes: {list(outputs.__dict__.keys())}")
            if isinstance(outputs, (tuple, list)):
                print(f"    Debug - Output length: {len(outputs)}")
                if len(outputs) > 0:
                    print(f"    Debug - First element type: {type(outputs[0])}")
                    if hasattr(outputs[0], "shape"):
                        print(f"    Debug - First element shape: {outputs[0].shape}")
            if hasattr(outputs, "last_hidden_state") and outputs.last_hidden_state is not None:
                token_embeddings = outputs.last_hidden_state
            elif isinstance(outputs, (tuple, list)) and len(outputs) > 0:
                token_embeddings = outputs[0]
            elif hasattr(outputs, "logits"):
                token_embeddings = outputs.logits
            else:
                print("    ⚠️  Could not extract embeddings from output")
                print(f"    Output type: {type(outputs)}")
                if hasattr(outputs, "__dict__"):
                    print(f"    Available attributes: {list(outputs.__dict__.keys())}")
                return False
            print(f"    Token embeddings shape before pooling: {token_embeddings.shape}")
            attention_mask = inputs["attention_mask"]
            input_mask_expanded = (
                attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            )
            onnx_emb = (
                (token_embeddings * input_mask_expanded).sum(1)
                / input_mask_expanded.sum(1).clamp(min=1e-09)
            ).squeeze()
            print(f"    Pooled embedding shape: {onnx_emb.shape}")
            if onnx_emb.shape[-1] > 1024:
                print(f"    Truncating from {onnx_emb.shape[-1]} to 1024 dimensions")
                onnx_emb = onnx_emb[..., :1024]
            onnx_emb_np = (
                onnx_emb.detach().cpu().numpy() if hasattr(onnx_emb, "cpu") else onnx_emb.numpy()
            )
            onnx_emb_np = onnx_emb_np / np.linalg.norm(onnx_emb_np)
            print(f"    Original embedding shape: {orig_emb.shape}")
            print(f"    ONNX embedding shape: {onnx_emb_np.shape}")
            print(f"    Original first 5 values: {orig_emb[:5]}")
            print(f"    ONNX first 5 values: {onnx_emb_np[:5]}")
            print(f"    Original embedding norm: {np.linalg.norm(orig_emb):.6f}")
            print(f"    ONNX embedding norm: {np.linalg.norm(onnx_emb_np):.6f}")
            similarity = np.dot(orig_emb, onnx_emb_np)
            print(f"    Text {i} similarity: {similarity:.6f}")
            if similarity < 0.99:
                print(f"    ⚠️  Low similarity detected: {similarity:.6f}")
                return False
        print("✅ Validation successful! Embeddings match.")
    except Exception as e:
        import traceback

        print(f"❌ Validation failed: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False
    else:
        return True


def create_model_card(output_dir: Path, original_model_id: str) -> None:
    """Create model card for HuggingFace.

    Args:
        output_dir: Directory containing ONNX model
        original_model_id: Original model ID
    """
    model_card = f"""---\nlicense: apache-2.0\nlibrary_name: sentence-transformers\ntags:\n  - sentence-transformers\n  - feature-extraction\n  - sentence-similarity\n  - transformers\n  - onnx\nbase_model: {original_model_id}\n---\n\n# {original_model_id.split("/")[-1]} - ONNX\n\nThis is an ONNX-converted version of [{original_model_id}](https://huggingface.co/{original_model_id}) optimized for use with [FastEmbed](https://github.com/qdrant/fastembed).\n\n## Model Details\n\n- **Base Model**: {original_model_id}\n- **Format**: ONNX\n- **Task**: Feature Extraction / Sentence Embeddings\n- **License**: Apache 2.0\n\n## Usage\n\n### With ONNX Runtime\n\n```python\nfrom optimum.onnxruntime import ORTModelForFeatureExtraction\nfrom transformers import AutoTokenizer\nimport torch\n\n# Load model and tokenizer\nmodel = ORTModelForFeatureExtraction.from_pretrained("knitli/voyage-4-nano-onnx", providers=["CUDAExecutionProvider", {"enable_cuda_graph": True}])\ntokenizer = AutoTokenizer.from_pretrained("knitli/voyage-4-nano-onnx")\n\n# Encode text\ntexts = ["This is an example sentence", "Another example"]\ninputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")\noutputs = model(**inputs)\n\n# Mean pooling\ntoken_embeddings = outputs.last_hidden_state\nattention_mask = inputs["attention_mask"]\ninput_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()\nembeddings = (token_embeddings * input_mask_expanded).sum(1) / input_mask_expanded.sum(1).clamp(min=1e-9)\n\n# Normalize\nembeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)\n```\n\n### With FastEmbed (once added to registry)\n\n```python\nfrom fastembed import TextEmbedding\n\nmodel = TextEmbedding("knitli/voyage-4-nano-onnx")\nembeddings = model.embed(["This is an example sentence"])\n```\n\n## Conversion\n\nThis model was converted to ONNX using [Optimum](https://huggingface.co/docs/optimum/):\n\n```bash\noptimum-cli export onnx --model {original_model_id} --task feature-extraction ./output\n```\n\n## Performance\n\nONNX models typically provide:\n- 2-4x faster inference than PyTorch\n- Lower memory footprint\n- Better deployment flexibility\n\n## Original Model\n\nFor the original PyTorch model, see [{original_model_id}](https://huggingface.co/{original_model_id}).\n\n## License\n\nThis model is licensed under Apache 2.0, same as the original model.\n"""
    readme_path = output_dir / "README.md"
    readme_path.write_text(model_card)
    print(f"📝 Model card created at {readme_path}")


def upload_to_huggingface(output_dir: Path, repo_id: str) -> bool:
    """Upload model to HuggingFace Hub.

    Args:
        output_dir: Directory containing ONNX model
        repo_id: HuggingFace repo ID (e.g., 'username/model-name')

    Returns:
        True if upload successful
    """
    try:
        from huggingface_hub import HfApi, create_repo

        print(f"\n📤 Uploading to HuggingFace: {repo_id}...")
        try:
            create_repo(repo_id, exist_ok=True)
            print(f"  - Repository created/verified: {repo_id}")
        except Exception as e:
            print(f"  ⚠️  Repo creation warning: {e}")
        api = HfApi()
        api.upload_folder(
            folder_path=output_dir,
            repo_id=repo_id,
            repo_type="model",
            commit_message="Add ONNX-converted voyage-4-nano model",
        )
        print(f"✅ Upload successful! View at: https://huggingface.co/{repo_id}")
    except ImportError:
        print("❌ huggingface-hub not installed. Install with: pip install huggingface-hub")
        return False
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        print("\nMake sure you're logged in:")
        print("  huggingface-cli login")
        return False
    else:
        return True


def main() -> int:
    """Main conversion workflow."""
    parser = argparse.ArgumentParser(
        description="Convert voyage-4-nano to ONNX for FastEmbed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model-id",
        default="voyageai/voyage-4-nano",
        help="HuggingFace model ID to convert (default: voyageai/voyage-4-nano)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./voyage-4-nano-onnx"),
        help="Output directory for ONNX model (default: ./voyage-4-nano-onnx)",
    )
    parser.add_argument(
        "--skip-validation", action="store_true", help="Skip embedding validation step"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validation on existing ONNX model (skip conversion)",
    )
    parser.add_argument(
        "--upload", action="store_true", help="Upload to HuggingFace after conversion"
    )
    parser.add_argument(
        "--hf-repo", help="HuggingFace repo ID for upload (e.g., knitli/voyage-4-nano-onnx)"
    )
    args = parser.parse_args()
    if args.skip_validation and args.validate_only:
        print("❌ Cannot use --skip-validation with --validate-only")
        return 1
    print("=" * 60)
    if args.validate_only:
        print("🔍 voyage-4-nano ONNX Validation")
    else:
        print("🚀 voyage-4-nano → ONNX Conversion")
    print("=" * 60)
    if args.validate_only:
        if not args.output_dir.exists():
            print(f"\n❌ ONNX model directory not found: {args.output_dir}")
            print("Run without --validate-only to convert first.")
            return 1
        print(f"\n📂 Using existing ONNX model at: {args.output_dir}")
    elif not convert_to_onnx(args.model_id, args.output_dir):
        return 1
    if not args.skip_validation and (not validate_conversion(args.model_id, args.output_dir)):
        print("\n⚠️  Validation failed. Review conversion before using.")
        return 1
    if not args.validate_only:
        create_model_card(args.output_dir, args.model_id)
    if args.upload:
        if not args.hf_repo:
            print("\n❌ --hf-repo required for upload")
            return 1
        if not upload_to_huggingface(args.output_dir, args.hf_repo):
            return 1
    print("\n" + "=" * 60)
    if args.validate_only:
        print("✅ Validation Complete!")
    else:
        print("✅ Conversion Complete!")
    print("=" * 60)
    print(f"\nONNX model location: {args.output_dir.absolute()}")
    if not args.validate_only:
        print("\nNext steps:")
        if not args.upload:
            print("  1. Review the model card (README.md)")
            print("  2. Upload to HuggingFace:")
            print(f"     python {__file__} --upload --hf-repo YOUR_USERNAME/voyage-4-nano-onnx")
        print("  3. Add to FastEmbed registry")
        print("  4. Submit PR to qdrant/fastembed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'\n    tokenizer = AutoTokenizer.from_pretrained(model_id)\n\n    # Embed queries with prompts\n    query = "What is the fastest route to 88 Kearny?"\n    prompt = "Represent the query for retrieving supporting documents: "\n    inputs = tokenizer(\n        prompt + query, return_tensors="pt", padding=True, truncation=True, max_length=32768\n    )\n    inputs = {k: v.to(device) for k, v in inputs.items()}\n    with torch.no_grad():\n        outputs = model.forward(**inputs)\n    embeddings = mean_pool(outputs.last_hidden_state, inputs["attention_mask"])\n    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)\n    '
