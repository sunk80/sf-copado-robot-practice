*** Settings ***
Documentation     Regression (negative): Salesforce must reject bad data.
...               The first tests use standard platform rules, so they work in any org.
...               The last one needs the optional custom rule from the README.
Resource          ../../resources/common.resource
Resource          ../../resources/business/records.resource
Suite Setup       Connect And Guard Org
Suite Teardown    Finish Suite
Test Tags         regression    negative    api


*** Test Cases ***
Account Without Name Is Rejected
    [Tags]    account
    Create Record Should Fail    Account    REQUIRED_FIELD_MISSING    Name=${EMPTY}    Industry=Banking

Contact Without Last Name Is Rejected
    [Tags]    contact
    Create Record Should Fail    Contact    REQUIRED_FIELD_MISSING    FirstName=NoLastName

Contact With Invalid Email Is Rejected
    [Tags]    contact
    ${last}=    Unique Name    ${TEST_PREFIX}-Con
    Create Record Should Fail    Contact    INVALID_EMAIL_ADDRESS    LastName=${last}    Email=not-an-email

Custom Rule: Insurance Account Needs A Phone
    [Documentation]    Requires the validation rule "RFPOC_Insurance_Requires_Phone" (see README).
    ...    Run with -v CUSTOM_RULES:True once the rule exists.
    [Tags]    account    custom-rule
    ${enabled}=    Is Truthy    ${CUSTOM_RULES}
    Skip If    not ${enabled}    Custom validation rule not enabled (set CUSTOM_RULES=True after creating it).
    ${name}=    Unique Name    ${TEST_PREFIX}-Acct
    Create Record Should Fail    Account    FIELD_CUSTOM_VALIDATION_EXCEPTION
    ...    Name=${name}    Industry=Insurance    Phone=${EMPTY}
