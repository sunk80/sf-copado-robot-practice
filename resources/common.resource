*** Settings ***
Documentation     Shared setup and teardown.
...               This is the ONLY file that knows how we connect and which UI library
...               is used, so moving to Copado Robotic Testing means changing it here.
Library           Collections
Library           ../libraries/SalesforceAPI.py
Library           ../libraries/SalesforceBulk.py
Library           ../libraries/Reconciliation.py
Library           ../libraries/TestData.py
Resource          variables/settings.resource


*** Keywords ***
Connect And Guard Org
    [Documentation]    Suite Setup for every suite: connect via API and refuse production orgs.
    Connect To Salesforce    ${SF_ORG_ALIAS}
    Assert Safe Org    allow_production=${ALLOW_PRODUCTION}

Ensure Salesforce UI Is Open
    [Documentation]    Opens one logged-in browser per suite (reused by every UI test).
    ${open}=    Get Variable Value    $UI_SESSION_OPEN    ${False}
    IF    not ${open}
        Open Salesforce In Browser    ui_library=${UI_LIBRARY}    browser=${BROWSER}    headless=${HEADLESS}
        SetConfig    DefaultTimeout    ${UI_TIMEOUT}
        SetConfig    ShadowDOM    True
        VerifyText    Home    timeout=60s
        Set Suite Variable    $UI_SESSION_OPEN    ${True}
    END

Close Salesforce UI
    ${open}=    Get Variable Value    $UI_SESSION_OPEN    ${False}
    IF    ${open}
        Run Keyword And Ignore Error    CloseAllBrowsers
        Set Suite Variable    $UI_SESSION_OPEN    ${False}
    END

Cleanup Test Data
    [Documentation]    Deletes every record created through the API keywords in this run.
    Delete Tracked Records

Finish Suite
    [Documentation]    Suite Teardown: clean up data even if tests failed, then close the browser.
    Run Keyword And Continue On Failure    Cleanup Test Data
    Close Salesforce UI
