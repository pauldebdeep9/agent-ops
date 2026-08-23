.PHONY: test baseline demo
test:
	python -m pytest tests/ -q
baseline:
	python -m iscops.eval.baseline
demo:
	python demo.py --all
