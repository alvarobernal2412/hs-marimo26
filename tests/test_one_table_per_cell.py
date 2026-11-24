"""Every table of a notebook is drawn by a cell of its own, so that its Visualize charts are its own."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ["00_lecture-initial-analysis.py", "01_assignment-initial-analysis.py", "03_assignment-process-map.py"]


def cells(notebook):
    tree = ast.parse((ROOT / "notebooks" / notebook).read_text(encoding="utf8"))
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


def calls(cell, owner, name):
    """The calls of `owner.name(...)` (or of `name(...)` when `owner` is None) in a cell."""
    found = []
    for node in ast.walk(cell):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if owner is None and getattr(function, "id", "") == name:
            found.append(node)
        if owner and isinstance(function, ast.Attribute) and function.attr == name and getattr(function.value, "id", "") == owner:
            found.append(node)
    return found


@pytest.mark.parametrize("notebook", NOTEBOOKS)
def test_no_cell_draws_two_tables(notebook):
    """marimo keeps the Visualize charts per cell: two tables drawn by one cell would share their charts."""
    for cell in cells(notebook):
        tables = calls(cell, "du", "table")
        assert len(tables) <= 1, f"{notebook}, line {cell.lineno}: {len(tables)} tables in one cell"
        if tables:  # and the table is shown by the cell that makes it: its charts are kept under that cell
            shown = cell.body[-2] if isinstance(cell.body[-1], ast.Return) else cell.body[-1]
            assert isinstance(shown, ast.Expr), f"{notebook}, line {cell.lineno}: the table is made here but shown by another cell"


@pytest.mark.parametrize("notebook, tables", [("01_assignment-initial-analysis.py", 14), ("03_assignment-process-map.py", 1)])
def test_every_recorded_table_has_a_name_of_its_own_written_out(notebook, tables):
    """A table's cell is found by the `artifact_name` in it (`ak.chart_cells`), and its charts are kept by that name."""
    names = []
    for cell in cells(notebook):
        for table in calls(cell, None, "show_table"):
            name = next(k.value for k in table.keywords if k.arg == "artifact_name")
            assert isinstance(name, ast.Constant) and isinstance(name.value, str), f"line {cell.lineno}: the name is not written out"
            names.append(name.value)
    assert len(names) == len(set(names)) == tables


@pytest.mark.parametrize("notebook", ["00_lecture-initial-analysis.py", "01_assignment-initial-analysis.py", "03_assignment-process-map.py"])
def test_the_library_that_comes_with_the_notebooks_is_found_before_the_installed_one(notebook):
    """`notebooks/vendor` goes on the path before anything of marimo-pmprov is imported (see build/vendor_library.py)."""
    source = (ROOT / "notebooks" / notebook).read_text(encoding="utf8")
    on_the_path = source.index('_sys.path.insert(0, str(_vendor))')
    assert 0 < source.index('_vendor = HERE / "vendor"') < on_the_path
    imports = [i for i in range(len(source)) if source.startswith("from provenance_widget", i)]
    assert imports and all(at > on_the_path for at in imports)
