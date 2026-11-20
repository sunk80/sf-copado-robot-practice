*** Settings ***
Documentation     Business-level data keywords. Tests call these, never the raw libraries,
...               so a change in tooling never touches the test cases.
Resource          ../common.resource


*** Keywords ***
Create Test Account
    [Documentation]    Creates an Account via API with a unique name. Extra fields are optional.
    ...    Returns the record Id. A Phone is always set so the optional
    ...    "Insurance accounts need a phone" validation rule is satisfied.
    [Arguments]    &{fields}
    IF    'Name' not in $fields
        ${name}=    Unique Name    ${TEST_PREFIX}-Acct
        Set To Dictionary    ${fields}    Name=${name}
    END
    IF    'Phone' not in $fields
        Set To Dictionary    ${fields}    Phone=555-0100
    END
    ${id}=    Create Record    Account    &{fields}
    RETURN    ${id}

Create Test Contact
    [Documentation]    Creates a Contact linked to an Account. Returns the record Id.
    [Arguments]    ${account_id}    &{fields}
    IF    'LastName' not in $fields
        ${last}=    Unique Name    ${TEST_PREFIX}-Con
        Set To Dictionary    ${fields}    LastName=${last}
    END
    ${id}=    Create Record    Contact    AccountId=${account_id}    &{fields}
    RETURN    ${id}

Account Should Be Created With Industry
    [Documentation]    Template keyword for data-driven tests.
    [Arguments]    ${industry}
    ${id}=    Create Test Account    Industry=${industry}
    Verify Record Fields    Account    ${id}    Industry=${industry}
