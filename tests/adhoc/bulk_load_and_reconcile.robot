*** Settings ***
Documentation     Adhoc / one-time: bulk load a CSV with Bulk API 2.0, reconcile it
...               against the org with SOQL, spot-check a few records in the UI,
...               then roll back unless KEEP=True.
...
...               Examples:
...               robot --argumentfile config/adhoc.args --include bulk -v ROWS:300 tests/adhoc
...               robot --argumentfile config/adhoc.args --include bulk -v FILE:data/adhoc/sample_accounts.csv tests/adhoc
...               robot --argumentfile config/adhoc.args --include bulk -v DRY_RUN:True -v FILE:my.csv tests/adhoc
Resource          ../../resources/common.resource
Resource          ../../resources/business/ui.resource
Suite Setup       Connect And Guard Org
Suite Teardown    Close Salesforce UI
Test Tags         adhoc


*** Variables ***
${FILE}             ${EMPTY}    # CSV to load; empty = generate synthetic Accounts
${OBJECT}           Account
${OPERATION}        insert      # insert | update | upsert
${EXTERNAL_ID}      ${EMPTY}    # external Id field, needed for upsert
${ROWS}             200         # rows to generate when FILE is empty
${MAX_ROWS}         1000        # Developer Edition has ~5 MB storage
${RECON_SAMPLE}     0           # 0 = reconcile every row
${UI_SAMPLE}        3           # records to open in the UI (0 = skip)
${KEEP}             False       # False = delete created records afterwards
${DRY_RUN}          False       # True = pre-check only, load nothing


*** Test Cases ***
Bulk Load And Reconcile
    [Tags]    bulk
    ${job}=    Set Variable    ${NONE}    # so the teardown works even if loading never starts
    ${file}=    Resolve Source File
    ${pre}=    Precheck Bulk File    ${file}    ${OBJECT}    ${OPERATION}    ${EXTERNAL_ID}    ${MAX_ROWS}
    ${dry}=    Is Truthy    ${DRY_RUN}
    IF    ${dry}    Pass Execution    Dry run: ${pre}[rows] row(s) passed pre-check. Nothing loaded.
    ${job}=    Run Bulk Job    ${OBJECT}    ${OPERATION}    ${file}    ${EXTERNAL_ID}
    ${recon}=    Reconcile Bulk Load    ${job}    sample_size=${RECON_SAMPLE}
    Log    Reconciliation report: ${recon}[report_file]    console=True
    Reconciliation Should Pass    ${recon}
    Bulk Job Should Succeed    ${job}
    Spot Check Loaded Records In UI    ${job}[success_file]    ${UI_SAMPLE}
    [Teardown]    Rollback Bulk Job    ${job}    keep=${KEEP}


*** Keywords ***
Resolve Source File
    IF    '${FILE}' != '${EMPTY}'    RETURN    ${FILE}
    Should Be Equal    ${OBJECT}    Account    msg=Synthetic data is only generated for Account; pass FILE for other objects.
    ${run}=    Get Run Id
    ${path}=    Generate Account Csv    results/adhoc/generated_accounts_${run}.csv    ${ROWS}    ${TEST_PREFIX}
    RETURN    ${path}

Spot Check Loaded Records In UI
    [Arguments]    ${success_file}    ${count}
    IF    ${count} == 0    RETURN
    ${rows}=    Pick Sample Rows    ${success_file}    ${count}
    FOR    ${row}    IN    @{rows}
        Open Record Page    ${OBJECT}    ${row}[sf__Id]
        IF    'Name' in $row    UI Should Show    ${row}[Name]
    END
