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
    [Documentation]    Opens the Related tab if the page layout has one. Some layouts (e.g. Sales Console)
    ...                have no such tab and show related lists in a side panel instead.
    ${clicked}    ${msg}=    Run Keyword And Ignore Error    ClickText    Related    partial_match=False    timeout=5s
    IF    '${clicked}' == 'FAIL'    Log    Related tab not found (related lists may be in a side panel): ${msg}

UI Should Show
    [Documentation]    Text is visible somewhere on the current page.
    [Arguments]    ${text}
    VerifyText    ${text}

UI Field Should Show
    [Documentation]    Field label and its value are both shown on the record page. Not anchored on purpose:
    ...                layouts like Sales Console show the same field in several panels, so an anchor on the
    ...                label matches more than one element and QWeb refuses it.
    [Arguments]    ${label}    ${value}
    VerifyText    ${label}
    VerifyText    ${value}

Edit Field In UI
    [Documentation]    Uses the record page Edit button, types a new value and saves.
    [Arguments]    ${label}    ${value}
    ClickText    Edit    partial_match=False
    TypeText    ${label}    ${value}
    ClickText    Save    partial_match=False
    VerifyNoText    Cancel
