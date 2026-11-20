*** Settings ***
Documentation     Adhoc / one-time: remove leftover framework data (records whose name starts
...               with the TEST_PREFIX). Useful because a Developer Edition only has ~5 MB.
...               Contacts under deleted Accounts are removed by Salesforce automatically.
...
...               robot --argumentfile config/adhoc.args --include cleanup -v DRY_RUN:True tests/adhoc
Resource          ../../resources/common.resource
Suite Setup       Connect And Guard Org
Test Tags         adhoc


*** Variables ***
${DRY_RUN}          False


*** Test Cases ***
Delete Leftover Test Accounts
    [Tags]    cleanup
    ${rows}=    Query Records    SELECT Id FROM Account WHERE Name LIKE '${TEST_PREFIX}-%'
    ${ids}=    Evaluate    [r['Id'] for r in $rows]
    ${count}=    Get Length    ${ids}
    Log    Found ${count} leftover Account(s) named ${TEST_PREFIX}-*    console=True
    ${dry}=    Is Truthy    ${DRY_RUN}
    IF    ${dry} or ${count} == 0    Pass Execution    Nothing deleted (dry run or no data).
    ${job}=    Bulk Delete Ids    Account    ${ids}
    Bulk Job Should Succeed    ${job}
    ${left}=    Get Record Count    Account    Name LIKE '${TEST_PREFIX}-%'
    Should Be Equal As Integers    ${left}    0
