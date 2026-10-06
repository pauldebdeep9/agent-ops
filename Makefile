.PHONY: test baseline audit mutate run transcripts
test:
	python -m pytest tests/ -q
baseline:
	python -m iscops.eval.baseline
audit:
	python -m iscops.eval.audit
mutate:
	python scripts/mutate.py
run:
	python -m iscops.eval.cli
transcripts:
	python -m iscops.eval.transcript
