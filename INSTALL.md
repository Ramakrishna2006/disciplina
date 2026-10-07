# Disciplina — Installation & Running Guide

Everything runs on a normal laptop CPU (no GPU needed). The only library is **NumPy**.
Trained models are included in `artifacts/`, so you can chat with the model straight after installing.

---

## 1. Install Python (once)

**Windows**
1. Download Python 3.10 or newer (3.12 recommended) from https://www.python.org/downloads/
2. Run the installer and **tick "Add python.exe to PATH"** on the first screen, then click *Install Now*.
3. Open **Command Prompt** (Windows key, type `cmd`, Enter) and check:
   ```
   python --version
   pip --version
   ```

**Mac**: install from python.org, open *Terminal*, and use `python3` / `pip3` wherever this guide says `python` / `pip`.
**Linux**: `sudo apt install python3 python3-venv python3-pip`, then use `python3`.

## 2. Get the project

**From GitHub:** open https://github.com/Ramakrishna2006/disciplina, click the green **Code** button → **Download ZIP**, then extract it.
Or, with Git installed:

```
git clone https://github.com/Ramakrishna2006/disciplina.git
cd disciplina
```

Open a terminal **inside** the project folder (the one containing `main.py`):
- Windows: open the folder in File Explorer, click the address bar, type `cmd`, press Enter.
- Or: `cd path\to\disciplina`

## 3. Create a virtual environment and install NumPy (once)

```
python -m venv venv
```

Activate it:

| System | Command |
|---|---|
| Windows Command Prompt | `venv\Scripts\activate` |
| Windows PowerShell | `venv\Scripts\Activate.ps1` |
| Mac / Linux | `source venv/bin/activate` |

You will see `(venv)` at the start of the line. Then:

```
pip install -r requirements.txt
python -c "import numpy; print(numpy.__version__)"
```

## 4. Check that everything works (about 1 minute)

```
python main.py test
```

It runs the three test files and ends with `ALL TESTS PASSED`. You can also run them one at a time:
`python tests/test_gradients.py`, `python tests/test_tokenizer.py`, `python tests/test_model.py`.
Each prints lines ending in `OK`. The first proves the hand-written backpropagation is mathematically correct, the
second that the tokenizer is lossless, and the third that the trained models answer all 60 held-out questions
correctly without forgetting (about 20 seconds).

## 5. Run the project

Everything is one command, `python main.py <command>`:

| Command | Time | What it does |
|---|---|---|
| `python main.py chat` | instant | Ask questions, e.g. `Where does Asha live?` → `Indore`. Ctrl + C to quit |
| `python main.py chat --base` | instant | The pre-trained model: type a sentence start such as `Meera loves` |
| `python main.py chat --base --temperature 0.8 --top_k 10` | instant | Same, with random sampling instead of greedy decoding |
| `python main.py eval` | ~1 min | Tokenizer examples, learned embeddings, prompt-engineering comparison, evaluation table |
| `python main.py data` | seconds | Re-creates the dataset files in `data/` and `DATASET.md` |
| `python main.py train` | ~30 min | Re-trains everything from zero and overwrites `artifacts/` |
| `python main.py train --no-replay --dir no_replay` | ~30 min | Ablation: fine-tunes without replay, to see catastrophic forgetting |
| `python main.py train --quick --dir test_run` | ~3 min | Fast smoke test into a separate folder (results will be poor) |

Training produces, in `artifacts/`: the tokenizer, three models, `results.json`, `run_log.txt`, and three
charts (`pretraining_loss.svg`, `finetuning_loss.svg`, `embeddings_pca.svg`) that open in any browser.

`python main.py --help` lists all commands and options.

## 6. Coming back another day

1. Open a terminal in the project folder.
2. Activate: `venv\Scripts\activate` (Mac/Linux: `source venv/bin/activate`).
3. Run any command above. Type `deactivate` when finished.

## 7. Using PyCharm or VS Code (optional)

- **PyCharm:** *File → Open* the project folder. Click `<No interpreter>` (bottom right) → *Add New Interpreter →
  Add Local Interpreter → Select existing* → choose `venv\Scripts\python.exe` (Mac/Linux: `venv/bin/python`).
- **VS Code:** install the **Python** extension, *File → Open Folder*, then `Ctrl + Shift + P` →
  *Python: Select Interpreter* → the one inside `venv`.

Use the built-in terminal to run the commands above. Do **not** open the `.npz` model files in the editor: they are
binary weights, and saving them from an editor corrupts them.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `'python' is not recognized` | PATH not ticked. Try `py` instead of `python`, or reinstall with "Add to PATH" |
| `python` opens the Microsoft Store | Settings → Apps → Advanced app settings → App execution aliases → turn off both Python entries |
| `'pip' is not recognized` | Use `python -m pip install -r requirements.txt` |
| PowerShell: "running scripts is disabled" | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, activate again (or use Command Prompt) |
| `No module named 'numpy'` | The environment is not active. Look for `(venv)` and activate again |
| `No module named 'llm'` | You are in the wrong folder. `cd` into the folder that contains `main.py` |
| `can't open file ... main.py` | Same: you are not inside the project folder |
| `No such file ... artifacts/...` | The trained models are missing. Run `python main.py train` once |
| Training is slow | Normal on older laptops (CPU only). Close other programs, or use `--quick` |
| pip fails on an office/college network | Try another network, or `pip install numpy --proxy http://<proxy>:<port>` |

## 9. No-install option: Google Colab

Open https://colab.research.google.com → *New notebook* → upload the project zip with the folder icon, then run:

```
!unzip -q disciplina.zip
%cd disciplina
!python tests/test_gradients.py
!python main.py eval
```

Colab already has NumPy. `!python main.py chat` also works: type your question in the input box under the cell.
