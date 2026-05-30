# Repo Notes

Project: `osu-skill-predictor`

This repository currently starts with planning artifacts only.
Do not assume production ML or API code exists unless it has been added later.

## JupyterLab

Start JupyterLab from the repository root:

```powershell
python -m jupyterlab --no-browser --ServerApp.root_dir="C:\Users\nayut\OneDrive\Документы\osu-skill-predictor"
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
