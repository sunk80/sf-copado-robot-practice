*** Settings ***
Documentation     Regression: UI and data stay in sync in both directions.
Resource          ../../resources/common.resource
Resource          ../../resources/business/records.resource
Resource          ../../resources/business/ui.resource
Suite Setup       Connect And Guard Org
Suite Teardown    Finish Suite
Test Tags         regression    account    ui


*** Test Cases ***
API Update Is Shown In UI
    ${id}=    Create Test Account    Industry=Banking
    Update Record    Account    ${id}    Industry=Technology    Phone=555-0142
    Open Record Page    Account    ${id}
    UI Field Should Show    Industry    Technology
    UI Field Should Show    Phone    555-0142

UI Edit Is Saved To The Database
    ${id}=    Create Test Account    Industry=Banking
    Open Record Page    Account    ${id}
    Edit Field In UI    Phone    555-0177
    Verify Record Fields    Account    ${id}    Phone=555-0177
