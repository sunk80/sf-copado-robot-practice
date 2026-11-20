*** Settings ***
Documentation     Default settings. Override any of them on the command line, e.g.
...               robot -v HEADLESS:True -v SF_ORG_ALIAS:myorg ...
...               In Copado Robotic Testing these become robot/suite variables.


*** Variables ***
${ENV}                  dev
${SF_ORG_ALIAS}         devorg
# UI keyword library. QWeb locally; switch to QForce in Copado Robotic Testing.
${UI_LIBRARY}           QWeb
${BROWSER}              chrome
${HEADLESS}             False
${UI_TIMEOUT}           20s
# Safety: tests refuse to run on a production org unless this is True.
${ALLOW_PRODUCTION}     False
# Every record this framework creates starts with this prefix (used by cleanup).
${TEST_PREFIX}          RFPOC
# Set True after adding the optional validation rule described in the README.
${CUSTOM_RULES}         False
