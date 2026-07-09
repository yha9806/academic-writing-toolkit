# Lost-in-Conversation Bench Cases

The bench now contains three public-safe writing-control cases. Each case uses the same three-way workflow comparison:

1. Baseline A: normal multi-turn chat editing.
2. Baseline B: consolidated single-turn prompting.
3. Treatment: `/thesis-control` with a spine card, edit contract, bounded edit, and drift audit.

| Case | Writing Pressure | Main Failure Mode |
| --- | --- | --- |
| `.` | Evidence boundaries in assisted revision | A fluent edit broadens a motivation section into a stronger model-reliability claim. |
| `method-limitation-boundary` | Make a methods limitation sound more confident | The limitation is weakened and the small sample starts to imply representative findings. |
| `evidence-boundary-literature` | Make a literature paragraph more forceful | Background sources are overstated as proof and product details leak into the motivation paragraph. |

The cases are not model benchmarks. They are author-control fixtures: each asks whether a human writer can inspect claim boundaries, evidence boundaries, scope discipline, and the final accept/revise decision without reconstructing a long chat history.
