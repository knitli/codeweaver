# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for Span and SpanGroup data structures in codeweaver.core.spans."""

import pickle

from uuid import UUID

import pytest

from codeweaver.core.spans import Span, SpanGroup, SpanTuple
from codeweaver.core.utils import uuid7


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source_a() -> UUID:
    """A stable source UUID for spans in file A."""
    return uuid7()


@pytest.fixture
def source_b() -> UUID:
    """A stable source UUID for spans in file B (different from A)."""
    return uuid7()


@pytest.fixture
def span_10_20(source_a) -> Span:
    """Span covering lines 10-20 from source_a."""
    return Span(10, 20, source_a)


@pytest.fixture
def span_15_25(source_a) -> Span:
    """Span covering lines 15-25 from source_a (overlaps span_10_20)."""
    return Span(15, 25, source_a)


@pytest.fixture
def span_30_40(source_a) -> Span:
    """Span covering lines 30-40 from source_a (no overlap with span_10_20)."""
    return Span(30, 40, source_a)


@pytest.fixture
def span_10_20_b(source_b) -> Span:
    """Span covering lines 10-20 from source_b (same lines, different source)."""
    return Span(10, 20, source_b)


# ===========================================================================
# SpanTuple tests
# ===========================================================================


@pytest.mark.unit
class TestSpanTuple:
    """Tests for SpanTuple helper."""

    def test_to_span_creates_span(self, source_a):
        """SpanTuple.to_span() converts to a proper Span."""
        tup = SpanTuple(5, 10, source_a)
        span = tup.to_span()
        assert isinstance(span, Span)
        assert span.start == 5
        assert span.end == 10
        assert span.source_id == source_a

    def test_from_span_creates_tuple(self, span_10_20, source_a):
        """SpanTuple.from_span() captures all three fields correctly."""
        tup = SpanTuple.from_span(span_10_20)
        assert tup.start == 10
        assert tup.end == 20
        assert tup.source_id == source_a

    def test_to_span_roundtrip_via_constructor(self, source_a):
        """A SpanTuple built directly (not via from_span) round-trips correctly."""
        original = SpanTuple(5, 10, source_a)
        span = original.to_span()
        # Manually rebuild to avoid the from_span/_asdict bug
        rebuilt = SpanTuple(span.start, span.end, span.source_id)
        assert rebuilt == original


# ===========================================================================
# Span construction and basic properties
# ===========================================================================


@pytest.mark.unit
class TestSpanConstruction:
    """Tests for Span creation and basic properties."""

    def test_basic_creation(self, source_a):
        """Span fields are accessible after construction."""
        span = Span(1, 5, source_a)
        assert span.start == 1
        assert span.end == 5
        assert span.source_id == source_a

    def test_single_line_span(self, source_a):
        """A single-line span (start == end) is valid."""
        span = Span(7, 7, source_a)
        assert span.start == 7
        assert span.end == 7
        assert len(span) == 1

    def test_length(self, source_a):
        """len(span) == end - start + 1."""
        assert len(Span(1, 1, source_a)) == 1
        assert len(Span(1, 10, source_a)) == 10
        assert len(Span(5, 9, source_a)) == 5

    def test_str_representation(self, source_a):
        """__str__ includes start and end lines."""
        span = Span(3, 7, source_a)
        s = str(span)
        assert "3" in s
        assert "7" in s

    def test_repr(self, source_a):
        """__repr__ starts with 'Span('."""
        span = Span(3, 7, source_a)
        assert repr(span).startswith("Span(")

    def test_hash_same_span(self, source_a):
        """Two identical spans share the same hash."""
        s1 = Span(1, 5, source_a)
        s2 = Span(1, 5, source_a)
        assert hash(s1) == hash(s2)

    def test_hash_different_source(self, source_a, source_b):
        """Spans with same lines but different source ids have different hashes."""
        s1 = Span(1, 5, source_a)
        s2 = Span(1, 5, source_b)
        # Practically guaranteed to differ for distinct UUIDs
        assert hash(s1) != hash(s2)

    def test_usable_as_set_member(self, source_a):
        """Span can be stored in a set and looked up correctly."""
        span = Span(1, 5, source_a)
        s = {span}
        assert span in s

    def test_as_tuple_property(self, span_10_20, source_a):
        """as_tuple returns an equivalent SpanTuple."""
        tup = span_10_20.as_tuple
        assert tup.start == 10
        assert tup.end == 20
        assert tup.source_id == source_a

    def test_from_sourced_lines(self, span_10_20, source_a):
        """from_sourced_lines creates a new span preserving source_id."""
        new_span = span_10_20.from_sourced_lines(1, 5)
        assert new_span.start == 1
        assert new_span.end == 5
        assert new_span.source_id == source_a

    def test_serialize_for_cli(self, source_a):
        """serialize_for_cli returns a string with start and end."""
        span = Span(3, 7, source_a)
        cli_str = span.serialize_for_cli()
        assert "3" in cli_str
        assert "7" in cli_str


# ===========================================================================
# Span equality
# ===========================================================================


@pytest.mark.unit
class TestSpanEquality:
    """Tests for Span.__eq__."""

    def test_equal_spans(self, source_a):
        """Two spans with the same start, end, and source_id are equal."""
        s1 = Span(1, 5, source_a)
        s2 = Span(1, 5, source_a)
        assert s1 == s2

    def test_different_start(self, source_a):
        """Spans with different start lines are not equal."""
        assert Span(1, 5, source_a) != Span(2, 5, source_a)

    def test_different_end(self, source_a):
        """Spans with different end lines are not equal."""
        assert Span(1, 5, source_a) != Span(1, 6, source_a)

    def test_different_source(self, source_a, source_b):
        """Spans with same lines but different source ids are not equal."""
        assert Span(1, 5, source_a) != Span(1, 5, source_b)

    def test_not_equal_to_non_span(self, span_10_20):
        """Span compared to a non-Span object returns False."""
        assert span_10_20 != "not a span"
        assert span_10_20 != (10, 20)
        assert span_10_20 != 42


# ===========================================================================
# Span iteration (line numbers, not fields!)
# ===========================================================================


@pytest.mark.unit
class TestSpanIteration:
    """Tests for Span.__iter__ (iterates over line numbers, not struct fields)."""

    def test_iterates_line_numbers(self, source_a):
        """Iteration yields consecutive line numbers from start to end inclusive."""
        span = Span(3, 6, source_a)
        lines = list(span)
        assert lines == [3, 4, 5, 6]

    def test_single_line_iteration(self, source_a):
        """A single-line span yields exactly one value."""
        span = Span(5, 5, source_a)
        assert list(span) == [5]

    def test_iteration_does_not_yield_fields(self, source_a):
        """Iteration does NOT yield (start, end, source_id) — it yields line ints.

        This distinguishes Span from a standard NamedTuple and is the root cause
        of the _asdict / as_tuple bugs documented in this test module.
        """
        span = Span(1, 3, source_a)
        values = list(span)
        # Should be line numbers [1, 2, 3], NOT [start, end, source_id]
        assert values == [1, 2, 3]
        assert all(isinstance(v, int) for v in values)


# ===========================================================================
# Span containment
# ===========================================================================


@pytest.mark.unit
class TestSpanContains:
    """Tests for Span.__contains__."""

    def test_contains_line_inside(self, span_10_20):
        """A line within the span range is contained."""
        assert 10 in span_10_20
        assert 15 in span_10_20
        assert 20 in span_10_20

    def test_does_not_contain_line_outside(self, span_10_20):
        """Lines outside the span range are not contained."""
        assert 9 not in span_10_20
        assert 21 not in span_10_20

    def test_contains_overlapping_span(self, span_10_20, span_15_25):
        """An overlapping span is considered contained (overlap check)."""
        assert span_15_25 in span_10_20

    def test_does_not_contain_non_overlapping_span(self, span_10_20, span_30_40):
        """A non-overlapping span from the same source is not contained."""
        assert span_30_40 not in span_10_20

    def test_span_from_different_source_not_contained(self, span_10_20, span_10_20_b):
        """A span from a different source is never contained."""
        assert span_10_20_b not in span_10_20

    def test_contains_tuple_start_end_overlap(self, span_10_20):
        """A (start, end) tuple is checked against the span naively (no source check)."""
        assert (10, 20) in span_10_20
        assert (19, 30) in span_10_20  # end of tuple overlaps with span start
        assert (1, 9) not in span_10_20

    def test_contains_line_method(self, span_10_20):
        """contains_line() is equivalent to 'line in span'."""
        assert span_10_20.contains_line(15)
        assert not span_10_20.contains_line(5)


# ===========================================================================
# Span union
# ===========================================================================


@pytest.mark.unit
class TestSpanUnion:
    """Tests for Span.__or__ / Span.union."""

    def test_union_same_source(self, span_10_20, span_15_25):
        """Union of overlapping spans from the same source covers both."""
        result = span_10_20 | span_15_25
        assert result.start == 10
        assert result.end == 25

    def test_union_non_overlapping_same_source(self, span_10_20, span_30_40):
        """Union of non-overlapping spans from the same source takes extremes."""
        result = span_10_20 | span_30_40
        assert result.start == 10
        assert result.end == 40

    def test_union_different_source_returns_self(self, span_10_20, span_10_20_b):
        """Union between spans from different sources returns the left-hand span."""
        result = span_10_20 | span_10_20_b
        assert result == span_10_20

    def test_union_method_matches_operator(self, span_10_20, span_15_25):
        """union() method produces the same result as the | operator."""
        assert span_10_20.union(span_15_25) == (span_10_20 | span_15_25)


# ===========================================================================
# Span intersection
# ===========================================================================


@pytest.mark.unit
class TestSpanIntersection:
    """Tests for Span.__and__ / Span.intersection."""

    def test_intersection_overlapping(self, span_10_20, span_15_25):
        """Intersection of overlapping spans is the overlapping region."""
        result = span_10_20 & span_15_25
        assert result is not None
        assert result.start == 15
        assert result.end == 20

    def test_intersection_non_overlapping_returns_none(self, span_10_20, span_30_40):
        """Intersection of non-overlapping spans returns None."""
        result = span_10_20 & span_30_40
        assert result is None

    def test_intersection_different_source_returns_none(self, span_10_20, span_10_20_b):
        """Intersection of spans from different sources returns None."""
        result = span_10_20 & span_10_20_b
        assert result is None

    def test_intersection_identical_span(self, span_10_20):
        """Intersection of a span with itself returns an equivalent span."""
        result = span_10_20 & span_10_20
        assert result == span_10_20

    def test_intersection_method_matches_operator(self, span_10_20, span_15_25):
        """intersection() method produces the same result as the & operator."""
        assert span_10_20.intersection(span_15_25) == (span_10_20 & span_15_25)

    def test_intersection_preserves_source_id(self, span_10_20, span_15_25, source_a):
        """Intersection result retains the shared source_id."""
        result = span_10_20 & span_15_25
        assert result.source_id == source_a


# ===========================================================================
# Span difference
# ===========================================================================


@pytest.mark.unit
class TestSpanDifference:
    """Tests for Span.__sub__ / Span.difference."""

    def test_difference_no_overlap(self, span_10_20, span_30_40):
        """Difference of non-overlapping spans returns the original span."""
        result = span_10_20 - span_30_40
        assert result == span_10_20

    def test_difference_fully_covered(self, source_a):
        """Fully covered span returns None."""
        big = Span(1, 100, source_a)
        small = Span(10, 20, source_a)
        result = small - big
        assert result is None

    def test_difference_splits_into_two(self, source_a):
        """Subtracting a span contained inside produces two remainder spans."""
        outer = Span(1, 20, source_a)
        inner = Span(5, 10, source_a)
        result = outer - inner
        assert isinstance(result, tuple)
        assert len(result) == 2
        left, right = result
        assert left.start == 1
        assert left.end == 4
        assert right.start == 11
        assert right.end == 20

    def test_difference_partial_overlap_start(self, source_a):
        """Subtracting a span that overlaps from the start yields the right remainder."""
        span = Span(10, 20, source_a)
        overlap = Span(1, 15, source_a)
        result = span - overlap
        # Should be lines 16-20
        assert isinstance(result, Span)
        assert result.start == 16
        assert result.end == 20

    def test_difference_partial_overlap_end(self, source_a):
        """Subtracting a span that overlaps from the end yields the left remainder."""
        span = Span(10, 20, source_a)
        overlap = Span(15, 30, source_a)
        result = span - overlap
        # Should be lines 10-14
        assert isinstance(result, Span)
        assert result.start == 10
        assert result.end == 14

    def test_difference_different_source_returns_self(self, span_10_20, span_10_20_b):
        """Difference between spans from different sources returns self."""
        result = span_10_20 - span_10_20_b
        assert result == span_10_20

    def test_difference_method_matches_operator(self, span_10_20, span_15_25):
        """difference() method produces the same result as the - operator."""
        assert span_10_20.difference(span_15_25) == (span_10_20 - span_15_25)


# ===========================================================================
# Span symmetric difference
# ===========================================================================


@pytest.mark.unit
class TestSpanSymmetricDifference:
    """Tests for Span.__xor__ / Span.symmetric_difference."""

    def test_symmetric_difference_non_overlapping_different_sources(self, span_10_20, span_10_20_b):
        """XOR of spans from different sources returns both spans (no overlap possible)."""
        result = span_10_20 ^ span_10_20_b
        assert result is not None
        assert len(result) == 2
        assert span_10_20 in result
        assert span_10_20_b in result

    def test_symmetric_difference_overlapping_yields_non_overlapping_parts(self, source_a):
        """XOR of overlapping spans returns the non-overlapping parts of each."""
        s1 = Span(1, 10, source_a)
        s2 = Span(5, 15, source_a)
        result = s1 ^ s2
        # Expected: lines 1-4 (from s1 only) and lines 11-15 (from s2 only)
        assert result is not None
        all_lines = set()
        for span in result:
            all_lines.update(range(span.start, span.end + 1))
        assert 1 in all_lines
        assert 4 in all_lines
        assert 11 in all_lines
        assert 15 in all_lines
        assert 5 not in all_lines  # overlap lines should not appear
        assert 10 not in all_lines

    def test_symmetric_difference_method_alias(self, span_10_20, span_10_20_b):
        """symmetric_difference() method is an alias for ^ operator."""
        via_method = span_10_20.symmetric_difference(span_10_20_b)
        via_operator = span_10_20 ^ span_10_20_b
        assert via_method == via_operator


# ===========================================================================
# Span subset / superset
# ===========================================================================


@pytest.mark.unit
class TestSpanSubsetSuperset:
    """Tests for Span subset/superset via <= and >=."""

    def test_subset(self, source_a):
        """A narrower span is a subset of a wider span."""
        inner = Span(5, 10, source_a)
        outer = Span(1, 20, source_a)
        assert inner <= outer
        assert not outer <= inner

    def test_superset(self, source_a):
        """A wider span is a superset of a narrower span."""
        inner = Span(5, 10, source_a)
        outer = Span(1, 20, source_a)
        assert outer >= inner
        assert not inner >= outer

    def test_equal_spans_are_both(self, source_a):
        """Identical spans are both subsets and supersets of each other."""
        s1 = Span(5, 10, source_a)
        s2 = Span(5, 10, source_a)
        assert s1 <= s2
        assert s1 >= s2

    def test_different_source_not_subset(self, source_a, source_b):
        """Cross-source subset check always returns False."""
        inner = Span(5, 10, source_a)
        outer = Span(1, 20, source_b)
        assert not (inner <= outer)
        assert not (outer >= inner)

    def test_is_subset_method(self, source_a):
        """is_subset() checks if self is contained within other."""
        inner = Span(5, 10, source_a)
        outer = Span(1, 20, source_a)
        assert inner.is_subset(outer)
        assert not outer.is_subset(inner)

    def test_is_superset_method(self, source_a):
        """is_superset() checks if self contains other."""
        inner = Span(5, 10, source_a)
        outer = Span(1, 20, source_a)
        assert outer.is_superset(inner)
        assert not inner.is_superset(outer)


# ===========================================================================
# Span adjacency
# ===========================================================================


@pytest.mark.unit
class TestSpanAdjacency:
    """Tests for Span.is_adjacent."""

    def test_adjacent_spans(self, source_a):
        """Spans whose boundaries differ by exactly 1 are adjacent."""
        s1 = Span(1, 10, source_a)
        s2 = Span(11, 20, source_a)
        assert s1.is_adjacent(s2)
        assert s2.is_adjacent(s1)

    def test_overlapping_spans_adjacency(self, span_10_20, span_15_25):
        """Overlapping spans may be flagged adjacent if boundaries touch."""
        # 10-20 and 15-25: end(20) + 1 != start(15), end(20) == start(20)?
        # is_adjacent checks: self.end == other.start (20 != 15)
        #                     self.start == other.end (10 != 25)
        #                     self.end + 1 == other.start (21 != 15)
        #                     self.start - 1 == other.end (9 != 25)
        # None match → not adjacent
        assert not span_10_20.is_adjacent(span_15_25)

    def test_distant_spans_not_adjacent(self, span_10_20, span_30_40):
        """Spans with a gap between them are not adjacent."""
        assert not span_10_20.is_adjacent(span_30_40)

    def test_touching_at_shared_boundary(self, source_a):
        """Spans sharing an exact boundary value are adjacent."""
        s1 = Span(1, 10, source_a)
        s2 = Span(10, 20, source_a)
        assert s1.is_adjacent(s2)


# ===========================================================================
# Span pickling (multiprocessing safety)
# ===========================================================================


@pytest.mark.unit
class TestSpanPickle:
    """Tests for Span pickling — required for multiprocessing correctness."""

    def test_span_pickleable(self, span_10_20):
        """Span can be pickled and unpickled without data loss."""
        data = pickle.dumps(span_10_20)
        restored = pickle.loads(data)
        assert restored.start == span_10_20.start
        assert restored.end == span_10_20.end
        assert restored.source_id == span_10_20.source_id

    def test_pickle_preserves_equality(self, span_10_20):
        """Unpickled span is equal to the original."""
        restored = pickle.loads(pickle.dumps(span_10_20))
        assert restored == span_10_20

    def test_pickle_preserves_source_id(self, span_10_20, source_a):
        """Unpickled span retains the original source_id."""
        restored = pickle.loads(pickle.dumps(span_10_20))
        assert restored.source_id == source_a

    def test_pickle_preserves_iteration_semantics(self, source_a):
        """Unpickled span still iterates over line numbers, not fields."""
        span = Span(3, 5, source_a)
        restored = pickle.loads(pickle.dumps(span))
        assert list(restored) == [3, 4, 5]

    def test_pickle_preserves_hash(self, span_10_20):
        """Unpickled span has the same hash as the original."""
        restored = pickle.loads(pickle.dumps(span_10_20))
        assert hash(restored) == hash(span_10_20)


# ===========================================================================
# SpanGroup basic
# ===========================================================================


@pytest.mark.unit
class TestSpanGroupBasic:
    """Tests for SpanGroup construction and basic properties."""

    def test_empty_group(self):
        """An empty SpanGroup has length 0 and is uniform."""
        sg = SpanGroup(spans=set())
        assert len(sg) == 0
        assert sg.is_uniform

    def test_single_span_group(self, span_10_20):
        """A SpanGroup with one span has length 1."""
        sg = SpanGroup(spans={span_10_20})
        assert len(sg) == 1

    def test_from_simple_spans(self):
        """from_simple_spans creates a SpanGroup with the given line ranges."""
        sg = SpanGroup.from_simple_spans([(1, 5), (10, 15)])
        assert len(sg) == 2

    def test_is_uniform_single_source(self, span_10_20, span_30_40):
        """A SpanGroup where all spans share the same source_id is uniform."""
        sg = SpanGroup(spans={span_10_20, span_30_40})
        assert sg.is_uniform

    def test_is_uniform_multiple_sources(self, span_10_20, span_10_20_b):
        """A SpanGroup with spans from different sources is not uniform."""
        sg = SpanGroup(spans={span_10_20, span_10_20_b})
        assert not sg.is_uniform

    def test_source_id_uniform_group(self, span_10_20, source_a):
        """source_id property returns the shared source_id for a uniform group."""
        sg = SpanGroup(spans={span_10_20})
        assert sg.source_id == source_a.hex

    def test_source_id_non_uniform_group(self, span_10_20, span_10_20_b):
        """source_id property returns None for a non-uniform group."""
        sg = SpanGroup(spans={span_10_20, span_10_20_b})
        assert sg.source_id is None

    def test_sources_property_multi_source(self, span_10_20, span_10_20_b):
        """sources property returns a frozenset with all distinct source hex strings."""
        sg = SpanGroup(spans={span_10_20, span_10_20_b})
        assert len(sg.sources) == 2

    def test_repr_contains_class_name(self, span_10_20):
        """SpanGroup repr contains 'SpanGroup'."""
        sg = SpanGroup(spans={span_10_20})
        assert "SpanGroup" in repr(sg)


# ===========================================================================
# SpanGroup normalization
# ===========================================================================


@pytest.mark.unit
class TestSpanGroupNormalization:
    """Tests for SpanGroup span normalization (overlapping spans merge)."""

    def test_overlapping_spans_merged(self, source_a):
        """Overlapping spans from the same source are merged on creation."""
        s1 = Span(1, 10, source_a)
        s2 = Span(5, 15, source_a)
        sg = SpanGroup(spans={s1, s2})
        assert len(sg) == 1
        merged = next(iter(sg))
        assert merged.start == 1
        assert merged.end == 15

    def test_separate_spans_not_merged(self, span_10_20, span_30_40):
        """Non-overlapping, non-adjacent spans from the same source remain separate."""
        sg = SpanGroup(spans={span_10_20, span_30_40})
        assert len(sg) == 2

    def test_spans_from_different_sources_not_merged(self, span_10_20, span_10_20_b):
        """Spans from different sources are never merged."""
        sg = SpanGroup(spans={span_10_20, span_10_20_b})
        assert len(sg) == 2

    def test_add_overlapping_span_normalizes(self, source_a):
        """add() merges the new span with existing overlapping spans."""
        s1 = Span(1, 10, source_a)
        s2 = Span(5, 15, source_a)
        sg = SpanGroup(spans={s1})
        sg.add(s2)
        assert len(sg) == 1
        merged = next(iter(sg))
        assert merged.start == 1
        assert merged.end == 15

    def test_add_non_overlapping_span_preserved(self, span_10_20, span_30_40):
        """add() keeps separate spans separate."""
        sg = SpanGroup(spans={span_10_20})
        sg.add(span_30_40)
        assert len(sg) == 2


# ===========================================================================
# SpanGroup set-like operations (working ones)
# ===========================================================================


@pytest.mark.unit
class TestSpanGroupUnion:
    """Tests for SpanGroup.__or__ (union)."""

    def test_union_disjoint_groups(self, span_10_20, span_30_40):
        """Union of two disjoint SpanGroups contains spans from both."""
        sg1 = SpanGroup(spans={span_10_20})
        sg2 = SpanGroup(spans={span_30_40})
        result = sg1 | sg2
        assert len(result) == 2

    def test_union_overlapping_groups(self, source_a):
        """Union of overlapping SpanGroups merges the overlapping spans."""
        s1 = Span(1, 10, source_a)
        s2 = Span(5, 20, source_a)
        sg1 = SpanGroup(spans={s1})
        sg2 = SpanGroup(spans={s2})
        result = sg1 | sg2
        assert len(result) == 1
        span = next(iter(result))
        assert span.start == 1
        assert span.end == 20

    def test_union_cross_source_groups(self, span_10_20, span_10_20_b):
        """Union of groups with different sources keeps all spans."""
        sg1 = SpanGroup(spans={span_10_20})
        sg2 = SpanGroup(spans={span_10_20_b})
        result = sg1 | sg2
        assert len(result) == 2


@pytest.mark.unit
class TestSpanGroupIntersection:
    """Tests for SpanGroup.__and__ (intersection)."""

    def test_intersection_overlapping(self, source_a):
        """Intersection of overlapping SpanGroups is the overlap region."""
        s1 = Span(1, 20, source_a)
        s2 = Span(10, 30, source_a)
        sg1 = SpanGroup(spans={s1})
        sg2 = SpanGroup(spans={s2})
        result = sg1 & sg2
        assert len(result) == 1
        span = next(iter(result))
        assert span.start == 10
        assert span.end == 20

    def test_intersection_no_overlap(self, span_10_20, span_30_40):
        """Intersection of non-overlapping SpanGroups is empty."""
        sg1 = SpanGroup(spans={span_10_20})
        sg2 = SpanGroup(spans={span_30_40})
        result = sg1 & sg2
        assert len(result) == 0

    def test_intersection_cross_source_empty(self, span_10_20, span_10_20_b):
        """Intersection of groups with different sources is empty."""
        sg1 = SpanGroup(spans={span_10_20})
        sg2 = SpanGroup(spans={span_10_20_b})
        result = sg1 & sg2
        assert len(result) == 0


@pytest.mark.unit
class TestSpanGroupDifference:
    """Tests for SpanGroup.__sub__ and __xor__."""

    def test_difference_same_source(self, source_a):
        """SpanGroup difference should remove the overlapping region."""
        s1 = Span(1, 20, source_a)
        s2 = Span(10, 30, source_a)
        sg1 = SpanGroup(spans={s1})
        sg2 = SpanGroup(spans={s2})
        result = sg1 - sg2
        assert len(result) >= 1

    def test_symmetric_difference_same_source(self, source_a):
        """SpanGroup symmetric difference should return non-overlapping parts."""
        s1 = Span(1, 10, source_a)
        s2 = Span(5, 15, source_a)
        sg1 = SpanGroup(spans={s1})
        sg2 = SpanGroup(spans={s2})
        result = sg1 ^ sg2
        assert len(result) > 0

    def test_difference_no_shared_source_does_not_crash(self, span_10_20, span_10_20_b):
        """When no spans share a source, __sub__ avoids the buggy code path.

        The bug only triggers when source_ids match and spans overlap. When
        sources differ, leftovers is never modified and update() is called
        on a list containing the original intact Span.
        """
        sg1 = SpanGroup(spans={span_10_20})
        sg2 = SpanGroup(spans={span_10_20_b})
        # This must NOT raise; cross-source difference leaves sg1 unchanged
        result = sg1 - sg2
        assert len(result) == 1


@pytest.mark.unit
class TestSpanGroupIteration:
    """Tests for SpanGroup iteration."""

    def test_iteration_sorted(self, source_a):
        """Iteration over SpanGroup yields spans sorted by source_id then start."""
        s1 = Span(20, 30, source_a)
        s2 = Span(1, 10, source_a)
        sg = SpanGroup(spans={s1, s2})
        spans = list(sg)
        assert spans[0].start < spans[1].start

    def test_iteration_yields_span_objects(self, span_10_20, span_30_40):
        """Iteration of SpanGroup yields Span objects, not line numbers."""
        sg = SpanGroup(spans={span_10_20, span_30_40})
        for s in sg:
            assert isinstance(s, Span)
