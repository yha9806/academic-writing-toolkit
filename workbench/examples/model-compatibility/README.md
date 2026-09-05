# Public-fixture model compatibility checks

These profiles are examples, not model recommendations or live-tested results.
Use model IDs and endpoints that your own account permits. Add profiles for any
provider returned by `awt --list-providers`; no runtime code change is needed.

```sh
# Plan only: no credentials needed and no requests sent.
python scripts/check-model-compatibility.py

# Opt in to one provider request using a fictional, embedded manuscript.
python scripts/check-model-compatibility.py --only claude-fable-5-1 --live --output final_output/fable-compatibility.json

# Opt in to five tasks per selected profile (ten requests in this example).
python scripts/check-model-compatibility.py --only glm-5-2 --only deepseek-v4-flash --all-workflows --live --output final_output/glm-deepseek-compatibility.json
```

Credentials come only from provider key environment variables. Never add API
key values to the JSON file. `api_key_env` may override the variable name.
Profile selection, endpoint overrides, format mode, and output budget use the
same validated configuration as the Workbench.

`output_contract_passed` means the returned review passed local structure and
evidence-reference checks. A missing-materials finding may legitimately have
`review_status=blocked` while its output contract passes. This runner does not
establish that a model understood the paper, found every issue, preserved author
voice, or improved writing. It neither modifies a manuscript nor supplies human
approval. Reports retain the model-returned review for an author to inspect.

To evaluate writing quality, add representative author-approved tasks, compare
outputs without model labels, and record actual author decisions separately.
The existing Lost-in-Conversation fixtures remain workflow-control examples;
do not relabel them as measured provider results.
