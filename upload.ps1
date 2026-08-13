py -3 -m mpremote mkdir :/apps/reaction
py -3 -m mpremote cp `
    '__init__.py' `
    'metadata.json' `
    'app.py' `
    'leds.py' `
    'touch.py' `
    'modes.py' `
    :/apps/reaction/

Write-Host "Deployed. Press the reboop button on the badge."
