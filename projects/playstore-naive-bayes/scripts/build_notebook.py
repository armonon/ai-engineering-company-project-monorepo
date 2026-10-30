"""Build an executed narrative notebook from the saved project artifacts."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "src" / "explore.ipynb"


def build() -> None:
    notebook = nbformat.v4.new_notebook(
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12"},
        }
    )
    notebook.cells = [
        nbformat.v4.new_markdown_cell(
            "# Google Play review classification with Naive Bayes\n\n"
            "This notebook is the reviewer-facing narrative for the official "
            "4Geeks assignment. The production implementation lives in `train.py`."
        ),
        nbformat.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n"
            "from IPython.display import Image, display\n\n"
            "project = Path.cwd().parent\n"
            "metrics = json.loads((project / 'artifacts/metrics.json').read_text())\n"
            "metrics"
        ),
        nbformat.v4.new_markdown_cell(
            "## Data and leakage controls\n\n"
            "The official 891-review dataset is stratified into train, validation, "
            "and final test partitions before `CountVectorizer` learns a vocabulary. "
            "Every transformer remains inside its scikit-learn pipeline."
        ),
        nbformat.v4.new_code_cell(
            "comparison = pd.read_csv(project / 'artifacts/validation_model_comparison.csv')\n"
            "comparison"
        ),
        nbformat.v4.new_code_cell(
            "display(Image(filename=project / 'reports/model_comparison.png'))"
        ),
        nbformat.v4.new_markdown_cell(
            "## Final held-out result\n\n"
            "Multinomial Naive Bayes was tuned with five-fold stratified CV. The "
            "Random Forest alternative won on validation F1, was refitted on the "
            "development partition, and evaluated once on the final test partition."
        ),
        nbformat.v4.new_code_cell(
            "display(Image(filename=project / 'reports/test_confusion_matrix.png'))\n"
            "metrics['test']"
        ),
        nbformat.v4.new_markdown_cell(
            "## Interpretation\n\n"
            "Token counts suit Multinomial Naive Bayes directly. BernoulliNB loses "
            "frequency information, while GaussianNB requires a dense matrix and a "
            "continuous Gaussian assumption that does not match sparse word counts. "
            "Random Forest won the validation comparison and is the final selected "
            "pipeline; the tuned Multinomial model is also preserved as the strongest "
            "required Naive Bayes implementation and the simpler explainable baseline."
        ),
        nbformat.v4.new_code_cell(
            "tokens = pd.read_csv(project / 'artifacts/informative_tokens.csv')\n"
            "tokens.head(12)"
        ),
    ]
    client = NotebookClient(
        notebook,
        timeout=180,
        kernel_name="python3",
        resources={"metadata": {"path": str(PROJECT_ROOT / "src")}},
    )
    executed = client.execute()
    NOTEBOOK_PATH.write_text(nbformat.writes(executed), encoding="utf-8")


if __name__ == "__main__":
    build()
