import os

scripts = [
    'run_llm_flow.py',
    'run_post_visit_flow.py',
    'run_calendar_test.py',
    'trigger_notification.py'
]

for script in scripts:
    path = f'/Users/apple/Downloads/Healthcare/backend/{script}'
    if not os.path.exists(path):
        continue
    with open(path, 'r') as f:
        content = f.read()
    
    # Replace old confirm call with the one sending symptoms
    content = content.replace(
        'conf_res = await client.post(f"/api/patient/appointments/{appt_id}/confirm", headers=pat_headers)',
        'conf_res = await client.post(f"/api/patient/appointments/{appt_id}/confirm", json={"symptoms_text": "I have a headache and I feel dizzy."}, headers=pat_headers)'
    )
    
    # For run_llm_flow.py, remove the extra submit_symptoms call
    if script == 'run_llm_flow.py':
        # Removing the block for submitting symptoms since it's now in confirm
        symp_block = """        # 3. Submit symptoms
        print("Submitting symptoms...")
        symp_res = await client.post(f"/api/patient/appointments/{appt_id}/symptoms", json={"symptoms_text": "I have a headache and I feel dizzy."}, headers=pat_headers)
        print("Symptom submission status:", symp_res.status_code)"""
        content = content.replace(symp_block, "")
        
    with open(path, 'w') as f:
        f.write(content)
        
print("Test scripts updated.")
