import {
  parseNaturalLanguageWire,
  mapDecisionToDisposition,
  isTaskIntentMismatch,
  DISPOSITION,
} from './src/types.js';

console.log('Testing P0 Transaction Integrity Frontend Parsing...');

const testA = `- Pasted amount: USD 142.50
- Route: US → US
- Beneficiary: Wholesale Grocery Distributors Inc.
- IP: 198.51.100.24
- Memo: Routine grocery invoice`;

const testB = `- Pasted amount: USD 49,500
- Route: US → GB
- Beneficiary: ACME CORPORATE SERVICES LTD
- IP: 203.0.113.35
- Memo: Corporate services invoice 7781`;

const testC = `- Pasted amount: USD 12,000
- Route: US → GB
- Beneficiary: NORTHSTAR INDUSTRIAL SUPPLIES LTD
- IP: 185.220.101.5
- Memo: Invoice 5521 for industrial supplies`;

// 1. Test A
const parsedA = parseNaturalLanguageWire(testA);
console.log('Test A Parsed:', {
  amount: parsedA.amount,
  counterparty_name: parsedA.counterparty_name,
  origin_country: parsedA.origin_country,
  destination_country: parsedA.destination_country,
  device_ip: parsedA.device_ip,
  memo: parsedA.memo,
});
if (parsedA.amount !== 142.50) throw new Error(`Test A amount mismatch: ${parsedA.amount} != 142.50`);
if (parsedA.counterparty_name !== 'Wholesale Grocery Distributors Inc.') throw new Error(`Test A beneficiary mismatch`);
if (parsedA.origin_country !== 'US' || parsedA.destination_country !== 'US') throw new Error(`Test A route mismatch`);
if (parsedA.device_ip !== '198.51.100.24') throw new Error(`Test A IP mismatch`);

const dispA = mapDecisionToDisposition('RELEASE_WITH_PROVENANCE', 'LOW', false, 'PAYMENT_INSTRUCTION');
if (dispA !== DISPOSITION.DISMISS) throw new Error(`Test A disposition should be DISMISS, got ${dispA}`);

// 2. Test B
const parsedB = parseNaturalLanguageWire(testB);
console.log('Test B Parsed:', {
  amount: parsedB.amount,
  counterparty_name: parsedB.counterparty_name,
  origin_country: parsedB.origin_country,
  destination_country: parsedB.destination_country,
  device_ip: parsedB.device_ip,
  memo: parsedB.memo,
});
if (parsedB.amount !== 49500) throw new Error(`Test B amount mismatch: ${parsedB.amount} != 49500`);
if (parsedB.counterparty_name !== 'ACME CORPORATE SERVICES LTD') throw new Error(`Test B beneficiary mismatch`);
if (parsedB.origin_country !== 'US' || parsedB.destination_country !== 'GB') throw new Error(`Test B route mismatch`);
if (parsedB.device_ip !== '203.0.113.35') throw new Error(`Test B IP mismatch`);

const dispB = mapDecisionToDisposition('ABSTAIN_FOR_HUMAN_REVIEW', 'MEDIUM', false, 'TRANSACTION_INVESTIGATION');
if (dispB !== DISPOSITION.ESCALATE) throw new Error(`Test B disposition should be ESCALATE, got ${dispB}`);
if (dispB === DISPOSITION.INPUT_MISMATCH) throw new Error(`Test B falsely returned INPUT_MISMATCH!`);

// 3. Test C
const parsedC = parseNaturalLanguageWire(testC);
console.log('Test C Parsed:', {
  amount: parsedC.amount,
  counterparty_name: parsedC.counterparty_name,
  origin_country: parsedC.origin_country,
  destination_country: parsedC.destination_country,
  device_ip: parsedC.device_ip,
  memo: parsedC.memo,
});
if (parsedC.amount !== 12000) throw new Error(`Test C amount mismatch: ${parsedC.amount} != 12000`);
if (parsedC.counterparty_name !== 'NORTHSTAR INDUSTRIAL SUPPLIES LTD') throw new Error(`Test C beneficiary mismatch`);
if (parsedC.origin_country !== 'US' || parsedC.destination_country !== 'GB') throw new Error(`Test C route mismatch`);
if (parsedC.device_ip !== '185.220.101.5') throw new Error(`Test C IP mismatch`);

const dispC = mapDecisionToDisposition('ABSTAIN_FOR_HUMAN_REVIEW', 'MEDIUM', false, 'TRANSACTION_INVESTIGATION');
if (dispC !== DISPOSITION.ESCALATE) throw new Error(`Test C disposition should be ESCALATE, got ${dispC}`);
if (dispC === DISPOSITION.INPUT_MISMATCH) throw new Error(`Test C falsely returned INPUT_MISMATCH!`);

// 4. Test 4 - Explicit sanctions match fixture input
const testSanctions = `- Pasted amount: USD 285,000
- Route: US → GB
- Beneficiary: TEST-SANCTIONED-ENTITY-002
- Bank: Test Settlement Bank
- IP: 185.220.101.5
- Memo: Test transaction for sanctions screening validation`;

const parsedSanctions = parseNaturalLanguageWire(testSanctions);
if (parsedSanctions.amount !== 285000) throw new Error(`Test 4 amount mismatch`);
if (parsedSanctions.counterparty_name !== 'TEST-SANCTIONED-ENTITY-002') throw new Error(`Test 4 beneficiary mismatch`);
if (parsedSanctions.origin_country !== 'US' || parsedSanctions.destination_country !== 'GB') throw new Error(`Test 4 route mismatch`);
if (parsedSanctions.settlement_institution !== 'Test Settlement Bank') throw new Error(`Test 4 bank mismatch`);

// 5. Test 5 - Natural Language Prose Rejection (Section 3 Defect A)
const explanatorySentence = `the disposition says the payment was released even though the sanctions probe is unavailable. Verify that the fast path is permitted under your declared policy when mandatory screening is unresolved.`;

const parsedExplanatory = parseNaturalLanguageWire(explanatorySentence);
console.log('Test 5 Parsed Explanatory Result:', parsedExplanatory);
if (!parsedExplanatory.is_unsupported_input) {
  throw new Error('Test 5 FAILED: Explanatory sentence was misclassified as a valid financial transaction!');
}
if (parsedExplanatory.input_type !== 'NATURAL_LANGUAGE_INQUIRY') {
  throw new Error(`Test 5 FAILED: Expected NATURAL_LANGUAGE_INQUIRY, got ${parsedExplanatory.input_type}`);
}
if (parsedExplanatory.amount || parsedExplanatory.origin_country || parsedExplanatory.destination_country) {
  throw new Error('Test 5 FAILED: Extracted false amount or country codes from explanatory prose!');
}

// Additional prose without payment intent should also be rejected
const randomProse = `Can you please check why the system flagged yesterday's batch and what the queue status is for review?`;
const parsedProse = parseNaturalLanguageWire(randomProse);
if (!parsedProse.is_unsupported_input) {
  throw new Error('General inquiry prose should be rejected from transaction parser');
}

// 6. SWIFT MT103 Parsing
const swiftMessage = `{1:F01TESTUS33AXXX0000000000}{2:I103TESTGB22XXXXN}{4:
:20:TRX123456789
:32A:261018USD75000,00
:50K:/12345678
ACME IMPORTERS US
:59:/98765432
GLOBAL EXPORTERS UK LTD
:70:INVOICE 9942 COMMERCIAL GOODS
-}`;
const parsedSwift = parseNaturalLanguageWire(swiftMessage);
if (parsedSwift.amount !== 75000) throw new Error(`SWIFT amount mismatch: ${parsedSwift.amount}`);
if (parsedSwift.currency !== 'USD') throw new Error(`SWIFT currency mismatch`);
if (parsedSwift.counterparty_name !== 'GLOBAL EXPORTERS UK LTD') throw new Error(`SWIFT beneficiary mismatch`);
if (parsedSwift.origin_country !== 'US' || parsedSwift.destination_country !== 'GB') throw new Error(`SWIFT route mismatch`);

// 7. IP Address Validation Safeguards
const validIPTest = `- Amount: USD 1,000\n- Route: US -> GB\n- Beneficiary: Alpha Corp\n- IP: 198.51.100.24`;
const parsedValidIP = parseNaturalLanguageWire(validIPTest);
if (parsedValidIP.device_ip !== '198.51.100.24') throw new Error(`Valid IP was not parsed: ${parsedValidIP.device_ip}`);

const invalidIPTest = `- Amount: USD 1,000\n- Route: US -> GB\n- Beneficiary: Alpha Corp\n- IP: 999.51.100.999`;
const parsedInvalidIP = parseNaturalLanguageWire(invalidIPTest);
if (parsedInvalidIP.device_ip !== null) throw new Error(`Invalid IP octet 999 was accepted!`);

// 8. Intent checks: Only genuine mismatches trigger INPUT_MISMATCH
if (isTaskIntentMismatch('TRANSACTION_INVESTIGATION')) throw new Error('TRANSACTION_INVESTIGATION must NOT be a task mismatch');
if (isTaskIntentMismatch('PAYMENT_INSTRUCTION')) throw new Error('PAYMENT_INSTRUCTION must NOT be a task mismatch');
if (!isTaskIntentMismatch('CYBERSECURITY_ANALYSIS')) throw new Error('CYBERSECURITY_ANALYSIS must be a task mismatch');
if (!isTaskIntentMismatch('POLICY_REVIEW')) throw new Error('POLICY_REVIEW must be a task mismatch');
if (!isTaskIntentMismatch('INVOICE_EXTRACTION')) throw new Error('INVOICE_EXTRACTION must be a task mismatch');

// 9. Precedence: manual edits vs pasted input
const basePayload = {
  amount: 500,
  counterparty_name: 'Manual Preset Beneficiary',
  counterparty_country: 'FR',
  origin_country: 'FR',
  device_ip: '192.0.2.1',
  memo: 'Manual preset memo',
};
const parsedOverBase = parseNaturalLanguageWire(testA, basePayload);
if (parsedOverBase.amount !== 142.50) throw new Error('Pasted amount did not override manual base amount');
if (parsedOverBase.counterparty_name !== 'Wholesale Grocery Distributors Inc.') throw new Error('Pasted beneficiary did not override base beneficiary');
if (parsedOverBase.destination_country !== 'US') throw new Error('Pasted destination did not override base destination');
if (parsedOverBase.device_ip !== '198.51.100.24') throw new Error('Pasted IP did not override base IP');

// 10. Unique Case and Transaction Identities
if (parsedA.transaction_id === parsedB.transaction_id) throw new Error('Transaction IDs must be unique across cases');
if (parsedB.transaction_id === parsedC.transaction_id) throw new Error('Transaction IDs must be unique across cases');
if (parsedA.case_id === parsedB.case_id) throw new Error('Case IDs must be unique across cases');
if (parsedB.case_id === parsedC.case_id) throw new Error('Case IDs must be unique across cases');

console.log('✅ ALL FRONTEND P0 TRANSACTION INTEGRITY TESTS PASSED!');

