# symbol-art

Turn images into font-aware ASCII art — locally, from a terminal-style web UI or the CLI.

<table>
  <tr>
    <td><img src="examples/behrad-input.png" width="360" alt="Input portrait"></td>
    <td><img src="examples/behrad-output.png" width="360" alt="ASCII art output"></td>
  </tr>
</table>

[View the raw ASCII output](examples/behrad-output.txt)

## Run

```bash
python -m pip install -r requirements.txt
python app.py
```

On Windows, after installing dependencies, you can also run `app.cmd`.

```bash
python symbol_art.py image.png -w 60
```

Everything runs locally on your machine.
