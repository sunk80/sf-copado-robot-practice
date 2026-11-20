*** Settings ***
Documentation     Smoke: the org is reachable and the core Account flow works
...               end to end - create via API, check with SOQL, check in Lightning UI.
Resource          ../../resources/common.resource
Resource          ../../resources/business/records.resource
Resource          ../../resources/business/ui.resource
Suite Setup       Connect And Guard Org
Suite Teardown    Finish Suite
Test Tags         smoke    account


*** Test Cases ***
Org Is Reachable And Has API Capacity
    [Tags]    api
    ${info}=    Get Org Info
    ${remaining}=    Get Daily Api Remaining
    Should Be True    ${remaining} > 500    Only ${remaining} API calls left today

Create Account Via API And Verify Via SOQL
    [Tags]    api
    ${name}=    Unique Name    ${TEST_PREFIX}-Acct
    ${id}=    Create Test Account    Name=${name}    Industry=Insurance    Phone=555-0101
    Verify Record Fields    Account    ${id}    Name=${name}    Industry=Insurance    Phone=555-0101

Account Created Via API Is Shown In Lightning UI
    [Tags]    ui
    ${name}=    Unique Name    ${TEST_PREFIX}-Acct
    ${id}=    Create Test Account    Name=${name}    Industry=Insurance
    Open Record Page    Account    ${id}
    UI Should Show    ${name}
    UI Field Should Show    Industry    Insurance
