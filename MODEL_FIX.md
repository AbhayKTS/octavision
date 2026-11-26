# Fix “Model not connected”

From the project root on the computer running the backend (Pi or laptop), run:

```bash
python tools/install_ppe_model.py
```

On Windows, use `py tools/install_ppe_model.py` if `python` does not work. The installer needs internet once. It downloads and verifies a public 22.5 MB construction PPE checkpoint and installs it into `weights/general.pt`, `weights/construction.pt` and `weights/road.pt`. Existing files are not overwritten. Then restart the backend and refresh the dashboard.

These three profiles **share one construction-trained model**, filtered using each profile's PPE list. They are not independently trained models. The model recognizes helmet, vest and gloves as well as explicit no-helmet/no-vest/no-glove classes; its performance must be validated on your own camera and environment. It is not a validated safety system. `chemical` and `mining` need suitable trained checkpoints at `weights/chemical.pt` and `weights/mining.pt`; do not copy this construction model to those names and claim chemical protection is detectable.

Source: https://huggingface.co/killuminati1/construction-ppe-yolov8, revision `ff33259`, `best.pt`, SHA-256 `31ef3ca04a17cf545f3fcfc64c4af8993a41d52ccc460e82aff01d5354603533`. The publisher lists Apache-2.0 for the model; the Ultralytics code and source datasets may have separate license terms. PyTorch `.pt` files can execute code on load: use only checkpoints from sources you trust. The SHA-256 pins the file but does not guarantee it is safe.

The model runs where the Flask backend runs, not where the browser runs. The Pi must have 64-bit Python, sufficient memory, cooling, dependencies from `backend/requirements.txt`, and an active network connection to download the weights. See `PI_SETUP.md` for laptop camera setup. Raspberry Pi speed is untested.
