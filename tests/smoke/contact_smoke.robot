*** Settings ***
Documentation     Smoke: a Contact can be created under an Account and appears on it.
Resource          ../../resources/common.resource
Resource          ../../resources/business/records.resource
Resource          ../../resources/business/ui.resource
Suite Setup       Connect And Guard Org
Suite Teardown    Finish Suite
Test Tags         smoke    contact


*** Test Cases ***
Contact Is Linked To Its Account
    [Tags]    api
    ${account_name}=    Unique Name    ${TEST_PREFIX}-Acct
    ${account_id}=    Create Test Account    Name=${account_name}
    ${contact_id}=    Create Test Contact    ${account_id}    FirstName=Smoke    Email=smoke.test@example.com
    Verify Record Field    Contact    ${contact_id}    Account.Name    ${account_name}
    Verify Record Fields    Contact    ${contact_id}    FirstName=Smoke    Email=smoke.test@example.com

Contact Appears In Account Related List
    [Tags]    ui
    ${account_id}=    Create Test Account
    ${last_name}=    Unique Name    ${TEST_PREFIX}-Con
    Create Test Contact    ${account_id}    LastName=${last_name}
    Open Record Page    Account    ${account_id}
    Show Related Tab
    UI Should Show    ${last_name}
