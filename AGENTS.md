# Repo Notes

Project: `osu-skill-predictor`

This repository currently starts with planning artifacts only.
Do not assume production ML or API code exists unless it has been added later.

## JupyterLab

Start JupyterLab from the repository root:

```powershell
python -m jupyterlab --no-browser --ServerApp.root_dir=.
```

Typical local URL:

```text
http://localhost:8888/lab?token=...
```

Stop JupyterLab:

```powershell
Get-Process python | Select-Object Id, Path
Stop-Process -Id <JUPYTER_PID>
```

If needed, confirm the server process by checking which Python process was started from the Jupyter command.

## Jupyter RTC

This repo uses JupyterLab Real-Time Collaboration via the `jupyter-collaboration` package.

Install or update it in the local user Python environment:

```powershell
python -m pip install --user jupyter-collaboration
```

After installing or updating RTC, restart JupyterLab. The collaboration backend is loaded through `jupyter_server_ydoc`.

Local RTC artifacts should not be committed:

- `.jupyter/`
- `.jupyter_ystore.db`
- `.jupyter_ystore.db-*`
- `*.log`

Environment note:

- Jupyter user-site executables typically live under `%APPDATA%\Python\Python310\Scripts`
- if `jupyter`, `jupyter-server`, or `jupyter-lab` are not found from the shell, use `python -m jupyterlab` or add that Scripts directory to `PATH`

## Markdown Paths

For repository Markdown files:

- prefer relative links and relative repo paths
- avoid absolute local filesystem paths such as `C:\...`
- use absolute local paths only when there is no reasonable relative alternative
