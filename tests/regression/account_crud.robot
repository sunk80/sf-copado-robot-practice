*** Settings ***
Documentation     Regression: full Account lifecycle through the API, checked with SOQL.
Resource          ../../resources/common.resource
Resource          ../../resources/business/records.resource
Suite Setup       Connect And Guard Org
Suite Teardown    Finish Suite
Test Tags         regression    account    api


*** Test Cases ***
Create Accounts Across Industries
    [Documentation]    Data-driven: one row per industry value.
    [Tags]    data-driven
    [Template]    Account Should Be Created With Industry
    Insurance
    Banking
    Technology
    Healthcare
    Manufacturing

Update Account Fields
    ${id}=    Create Test Account    Industry=Insurance
    Update Record    Account    ${id}    Phone=555-0199    NumberOfEmployees=250    Industry=Finance
    Verify Record Fields    Account    ${id}    Phone=555-0199    NumberOfEmployees=250    Industry=Finance

Delete Account
    ${id}=    Create Test Account
    Delete Record    Account    ${id}
    Record Should Not Exist    Account    ${id}

Deleting Account Also Deletes Its Contacts
    ${account_id}=    Create Test Account
    ${contact_id}=    Create Test Contact    ${account_id}
    Delete Record    Account    ${account_id}
    Record Should Not Exist    Contact    ${contact_id}

SOQL Count Matches Records Created
    ${marker}=    Unique Name    ${TEST_PREFIX}-Count
    FOR    ${i}    IN RANGE    3
        Create Test Account    Name=${marker}-${i}
    END
    ${count}=    Get Record Count    Account    Name LIKE '${marker}-%'
    Should Be Equal As Integers    ${count}    3
