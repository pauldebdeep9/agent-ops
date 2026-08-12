.PHONY: test baseline run transcripts
test:
	python -m pytest tests/ -q
baseline:
	python -m iscops.eval.baseline
run:
	python -m iscops.eval.cli
transcripts:
	python -m iscops.eval.transcript
