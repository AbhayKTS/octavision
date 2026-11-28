# Live detection reliability update

- Camera cleanup no longer stops the live stream when a still image preview changes.
- Live monitoring requires a camera belonging to the selected worksite and displays errors when saving an alert fails.
- Detection reporting validates site, camera, optional zone, confidence and site-specific violation classes.
- Alert polling detects the first new alert after an initially empty list; the live callback no longer plays a duplicate alarm.

Run `cd backend && python -m unittest discover -s tests -v` and `cd frontend && npm ci && npm run build`. Manual verification still needed: real laptop camera, sound after user interaction, trained model, snapshots, hardware and network disconnect. Alert suppression remains camera-and-PPE based, not worker-specific. This prototype is not a validated safety system. For model installation see MODEL_FIX.md and PI_SETUP.md.
