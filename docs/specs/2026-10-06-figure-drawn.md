# Float reviews: what a figure draws, not only what it says

Status: implemented on branch `feat/figure-drawn` (2026-10-06; T274 fails on main and passes here, six mutants of
the new code each caught by T274, the figure and table tests T239–T253 and T184 pass locally; CI not run; author
has not read this spec; not pushed)

## Problem

The review sheet (spec 2026-09-25-generated-copies-and-float-reviews) sets out what each float says in words: its
caption, TikZ node text and table notes. A diagram also says things with lines. An arrow claims that one element
acts on another; a brace claims that a set of boxes is one stage; a fitted box claims containment.

On one manuscript, a pipeline figure had right words and wrong lines:

- three flow arrows ran between bare coordinates in the gaps between columns, so the figure did not say which box
  fed which;
- four arrows rose from a band of manipulations at hand-placed x positions; three ended under a box the manipulation
  does not change;
- the measures were drawn as one box at the end of the pipeline, though some of them are taken at an earlier stage.

A review of the rendered page passed it. The sheet had listed every word and no line, and the words were right.

## Goal

Put each line a figure draws in front of the reviewer, named by the elements at its ends, and mark the ends that name
no element.

## Non-goals

- Judging whether an arrow is right. That is the method's question and the reviewer's call.
- Geometry from the PDF (whether an end touches a border, whether a line crosses a box).
- A failing exit for a marked end. A figure may point at a free label on purpose; the float is already unreviewed
  until someone looks, and the finding says how many lines are marked.
- TikZ beyond paths, nodes, coordinates, styles and fit: `\foreach`, pics, edges, matrices and macro expansion are
  not read, and the docstring says so.

## Decision

`audit-float-reviews.py` reads the TikZ in each float and the `.tex` files it pulls in, with styles from the float
and from the preamble:

- an arrow is a `\draw` (or `\path` with tips) whose options, followed through styles and the picture's own options,
  put a tip at an end;
- an end reaches an element when it names a node, a point on a drawn brace, or a coordinate defined from either,
  with offsets; it reaches none when it is only numbers, a `++` step or the bounding box; it is partly a number when
  one side of `A |- B` or `A -| B` is a number;
- an end built level with one element and in line with the element at the other end (`A -| B`, B at the other end)
  is named by A, so the arrow reads from A to B;
- a brace, a line joining two different elements, and a fitted group are listed; a rule, a frame (`rectangle`,
  `circle` and the like) and a plain `\path` are not.

The JSON payload carries `drawn` per float. The sheet adds a section under each float and two items to the
checklist: lines against the method, and excerpts against the source the caption names. The unreviewed finding
counts the marked lines.

## Acceptance

1. T274, on a synthetic figure: named ends unmarked; bare ends, a bounding-box start, a partly numeric start and a
   `++` end marked; a perpendicular start named by its own element; a joining line, a brace, an arrow from the brace
   tip and a fitted group listed; a rule, a frame and a plain path not listed; a picture-wide `->` applied and an
   explicit `-` honoured; the finding counts five marked lines of ten; the sheet carries the check and the list.
   T274 fails on main.
2. Mutants: every end treated as an element, the perpendicular rule removed, picture-wide tips ignored, frames listed,
   `++` steps treated as elements, braces not treated as elements. T274 catches each.
3. On the manuscript figure that prompted this (not in this repository), its first version reads with 7 of its 8
   lines marked and three of its four manipulation arrows ending at boxes they do not change; its revised version
   reads arrow by arrow from each manipulation to the element it changes.
4. Not yet: CI on Linux and Python 3.8; the installed copy under `~/.claude/skills` (it changes only after a merge
   and an install).
