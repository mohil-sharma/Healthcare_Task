<script lang="ts">
    import { onMount } from 'svelte';
    import { login, getAdminDoctors, createDoctorAdmin, updateDoctorAdmin, addDoctorLeaveAdmin } from '$lib/api';

    let token = '';
    let loggedIn = false;
    let doctors = [];
    
    // Login form state
    let email = 'admin@system.local';
    let password = 'admin123';
    let loginError = '';

    // Create doctor state
    let newDoc = { email: '', name: '', password: '', specialisation: '', slot_duration_minutes: 30 };

    // Leave day state
    let selectedDocId = '';
    let leaveDate = '';
    let leaveReason = '';
    let leaveResult = null;
    let leaveError = '';

    onMount(() => {
        token = localStorage.getItem('token') || '';
        if (token) {
            loggedIn = true;
            loadDoctors();
        }
    });

    async function handleLogin() {
        try {
            await login(email, password);
            loggedIn = true;
            token = localStorage.getItem('token') || '';
            loginError = '';
            loadDoctors();
        } catch (e) {
            loginError = 'Login failed. Check credentials.';
        }
    }

    function logout() {
        localStorage.removeItem('token');
        loggedIn = false;
        token = '';
        doctors = [];
    }

    async function loadDoctors() {
        try {
            doctors = await getAdminDoctors();
        } catch (e) {
            if (e.message.includes('Failed to fetch')) logout(); // basic 401 handling
            console.error(e);
        }
    }

    async function handleCreateDoctor() {
        try {
            await createDoctorAdmin(newDoc);
            alert('Doctor created!');
            newDoc = { email: '', name: '', password: '', specialisation: '', slot_duration_minutes: 30 };
            loadDoctors();
        } catch (e) {
            alert(e.message);
        }
    }

    async function toggleActive(doc) {
        try {
            await updateDoctorAdmin(doc.id, { is_active: !doc.is_active });
            loadDoctors();
        } catch (e) {
            alert('Failed to update status');
        }
    }

    async function updateWorkingHours(doc, hoursStr) {
        try {
            const hours = JSON.parse(hoursStr);
            await updateDoctorAdmin(doc.id, { working_hours: hours });
            alert('Working hours updated!');
            loadDoctors();
        } catch (e) {
            alert('Invalid JSON or update failed');
        }
    }

    async function handleAddLeave() {
        if (!selectedDocId || !leaveDate) return alert("Select doctor and date");
        leaveResult = null;
        leaveError = '';
        try {
            leaveResult = await addDoctorLeaveAdmin(selectedDocId, leaveDate, leaveReason);
            leaveDate = '';
            leaveReason = '';
        } catch (e) {
            leaveError = e.message;
        }
    }
</script>

<svelte:head>
    <title>Admin Dashboard</title>
</svelte:head>

<main class="container">
    <h1>Healthcare Admin Panel</h1>

    {#if !loggedIn}
        <section class="login-card">
            <h2>Admin Login</h2>
            {#if loginError}<p class="error">{loginError}</p>{/if}
            <form on:submit|preventDefault={handleLogin}>
                <label>Email: <input type="email" bind:value={email} required /></label>
                <label>Password: <input type="password" bind:value={password} required /></label>
                <button type="submit">Log in</button>
            </form>
        </section>
    {:else}
        <div class="header-actions">
            <span>Logged in as Admin</span>
            <button on:click={logout}>Log out</button>
        </div>

        <hr/>

        <section class="grid-layout">
            <!-- Left Column: Doctors List & Creation -->
            <div>
                <h2>Manage Doctors</h2>
                <div class="card">
                    <h3>Create New Doctor</h3>
                    <form on:submit|preventDefault={handleCreateDoctor} class="form-grid">
                        <input type="text" placeholder="Name" bind:value={newDoc.name} required />
                        <input type="email" placeholder="Email" bind:value={newDoc.email} required />
                        <input type="password" placeholder="Password" bind:value={newDoc.password} required />
                        <input type="text" placeholder="Specialisation" bind:value={newDoc.specialisation} required />
                        <input type="number" placeholder="Slot Mins" bind:value={newDoc.slot_duration_minutes} required />
                        <button type="submit">Create</button>
                    </form>
                </div>

                <h3>Existing Doctors</h3>
                {#each doctors as doc}
                    <div class="card doctor-card" class:inactive={!doc.is_active}>
                        <div class="doc-header">
                            <strong>{doc.name}</strong> ({doc.doctor_profile.specialisation})
                            <button class="toggle-btn" on:click={() => toggleActive(doc)}>
                                {doc.is_active ? 'Deactivate' : 'Activate'}
                            </button>
                        </div>
                        <div class="doc-details">
                            <div>Slot: {doc.doctor_profile.slot_duration_minutes}m</div>
                            <div>
                                Working Hours (JSON):<br/>
                                <textarea rows="3" on:change={(e) => updateWorkingHours(doc, e.target.value)}>
{JSON.stringify(doc.doctor_profile.working_hours, null, 2)}
                                </textarea>
                            </div>
                        </div>
                    </div>
                {/each}
            </div>

            <!-- Right Column: Leave Management -->
            <div>
                <h2>Leave Management</h2>
                <div class="card">
                    <h3>Mark Doctor on Leave</h3>
                    <form on:submit|preventDefault={handleAddLeave} class="stacked-form">
                        <select bind:value={selectedDocId} required>
                            <option value="">-- Select Doctor --</option>
                            {#each doctors as doc}
                                <option value={doc.id}>{doc.name}</option>
                            {/each}
                        </select>
                        
                        <input type="date" bind:value={leaveDate} required />
                        <input type="text" placeholder="Reason (optional)" bind:value={leaveReason} />
                        
                        <button type="submit">Record Leave & Cancel Appointments</button>
                    </form>

                    {#if leaveError}
                        <p class="error">{leaveError}</p>
                    {/if}

                    {#if leaveResult}
                        <div class="success-box">
                            <h4>Leave Recorded!</h4>
                            <p>Date: {leaveResult.leave_day.leave_date}</p>
                            <p><strong>{leaveResult.cancelled_appointments.length} appointments cancelled.</strong></p>
                            
                            {#if leaveResult.cancelled_appointments.length > 0}
                                <ul>
                                    {#each leaveResult.cancelled_appointments as appt}
                                        <li>
                                            Appt #{appt.id} | Patient ID: {appt.patient_id} | 
                                            {new Date(appt.slot_start).toLocaleTimeString()} - {new Date(appt.slot_end).toLocaleTimeString()}
                                        </li>
                                    {/each}
                                </ul>
                                <small>Notifications queued in notifications_log.</small>
                            {/if}
                        </div>
                    {/if}
                </div>
            </div>
        </section>
    {/if}
</main>

<style>
    :global(body) { font-family: system-ui, sans-serif; background: #f9fafb; color: #111827; margin: 0; padding: 20px; }
    .container { max-width: 1200px; margin: 0 auto; }
    .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .grid-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; align-items: start; }
    
    .login-card { max-width: 400px; margin: 50px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .login-card form { display: flex; flex-direction: column; gap: 15px; }
    
    input, select, textarea { padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; width: 100%; box-sizing: border-box; }
    button { background: #2563eb; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: 500; }
    button:hover { background: #1d4ed8; }
    
    .header-actions { display: flex; justify-content: space-between; align-items: center; }
    
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .form-grid button { grid-column: span 2; }
    .stacked-form { display: flex; flex-direction: column; gap: 15px; }
    
    .doctor-card { border-left: 4px solid #10b981; }
    .doctor-card.inactive { border-left-color: #ef4444; opacity: 0.7; }
    .doc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .toggle-btn { padding: 4px 8px; font-size: 0.8em; background: #4b5563; }
    
    .error { color: #ef4444; font-weight: bold; }
    .success-box { margin-top: 20px; padding: 15px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 4px; }
    .success-box ul { margin: 10px 0 0 20px; padding: 0; }
</style>
