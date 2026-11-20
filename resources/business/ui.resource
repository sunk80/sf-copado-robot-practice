*** Settings ***
Documentation     Lightning UI keywords written only with QWords (GoTo, ClickText,
...               TypeText, VerifyText). They run with QWeb locally and with QForce
...               in Copado Robotic Testing without changes.
Resource          ../common.resource


*** Keywords ***
Open Record Page
    [Documentation]    Opens the Lightning record page and shows the Details tab.
    [Arguments]    ${object}    ${record_id}
    Ensure Salesforce UI Is Open
    ${base}=    Get Instance Url
    GoTo    ${base}/lightning/r/${object}/${record_id}/view
    Show Details Tab

Show Details Tab
    ${clicked}    ${msg}=    Run Keyword And Ignore Error    ClickText    Details    partial_match=False    timeout=10s
    IF    '${clicked}' == 'FAIL'    Log    Details tab not clicked (layout may show details by default): ${msg}

Show Related Tab
    ClickText    Related    partial_match=False

UI Should Show
    [Documentation]    Text is visible somewhere on the current page.
    [Arguments]    ${text}
    VerifyText    ${text}

UI Field Should Show
    [Documentation]    Value is shown next to its field label on the record page.
    [Arguments]    ${label}    ${value}
    VerifyText    ${value}    anchor=${label}

Edit Field In UI
    [Documentation]    Uses the record page Edit button, types a new value and saves.
    [Arguments]    ${label}    ${value}
    ClickText    Edit    partial_match=False
    TypeText    ${label}    ${value}
    ClickText    Save    partial_match=False
    VerifyNoText    Cancel
