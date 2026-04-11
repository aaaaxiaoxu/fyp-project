<template>
  <v-app>
    <div class="main-view">
      <header class="app-header">
        <div class="header-left">
          <div class="brand" @click="goToGraph">SOCIOGRAPH</div>
          <button class="header-btn subtle" @click="goToGraph">Back To Graph</button>
        </div>

        <div class="header-center">
          <div class="workflow-step">
            <span class="step-num">Step 2-3/5</span>
            <span class="step-name">Simulation Control</span>
          </div>
        </div>

        <div class="header-right">
          <button class="header-btn subtle" :disabled="projectsLoading" @click="refreshProjects(selectedProjectId)">
            {{ projectsLoading ? 'Refreshing...' : 'Refresh Projects' }}
          </button>
          <span class="status-indicator" :class="statusClass">
            <span class="dot"></span>
            {{ statusText }}
          </span>
        </div>
      </header>

      <div v-if="pageError" class="page-error-banner">
        {{ pageError }}
      </div>

      <main class="content-area">
        <section class="panel-shell roster-shell">
          <div class="panel-header">
            <div class="panel-title-group">
              <span class="panel-title">AGENT ROSTER</span>
              <div class="panel-subtitle-row">
                <span class="panel-subtitle">{{ selectedProject?.name || 'Waiting for project selection' }}</span>
                <span v-if="selectedProject" :class="statusMeta(selectedProject.status).class">
                  {{ statusMeta(selectedProject.status).label }}
                </span>
                <span v-if="activeSimulationId" class="badge accent mono">{{ activeSimulationId }}</span>
              </div>
            </div>

            <div class="header-tools">
              <button class="tool-btn" :disabled="resultsLoading || !activeSimulationId" @click="refreshSimulationResults">
                {{ resultsLoading ? 'Loading...' : 'Refresh Results' }}
              </button>
            </div>
          </div>

          <div class="panel-body">
            <div class="summary-strip">
              <div class="summary-card">
                <span class="summary-value">{{ simulationProfiles.length }}</span>
                <span class="summary-label">AGENTS</span>
              </div>
              <div class="summary-card">
                <span class="summary-value">{{ graphData?.node_count || 0 }}</span>
                <span class="summary-label">ENTITY NODES</span>
              </div>
              <div class="summary-card">
                <span class="summary-value">{{ totalRounds || 0 }}</span>
                <span class="summary-label">TOTAL ROUNDS</span>
              </div>
              <div class="summary-card">
                <span class="summary-value">{{ totalRuntimeActions }}</span>
                <span class="summary-label">ACTIONS</span>
              </div>
            </div>

            <div v-if="resultsError" class="inline-error">
              {{ summarizeError(resultsError) }}
            </div>

            <template v-if="simulationProfiles.length">
              <div class="roster-toolbar">
                <input
                  v-model="profileSearch"
                  class="search-input"
                  type="text"
                  placeholder="Search name, @username, persona, topic, type"
                />
                <div class="toolbar-badges">
                  <span class="badge pending">Stable agent identifiers</span>
                  <span class="badge soft">Showing {{ filteredProfiles.length }} / {{ simulationProfiles.length }}</span>
                </div>
              </div>

              <div v-if="hotTopics.length" class="tag-section">
                <span class="tag-label">HOT TOPICS</span>
                <div class="tag-row">
                  <span v-for="topic in hotTopics" :key="topic" class="entity-tag">{{ topic }}</span>
                </div>
              </div>

              <div class="profile-grid">
                <article v-for="profile in filteredProfiles" :key="profile.user_id" class="profile-card">
                  <div class="profile-top">
                    <div class="profile-heading">
                      <h3>{{ profile.name }}</h3>
                      <p>{{ profile.source_entity_type || 'Entity' }}</p>
                    </div>
                    <span class="agent-pill">AGENT {{ profile.user_id }}</span>
                  </div>

                  <div class="profile-meta-row">
                    <span class="profile-username mono">@{{ profile.username }}</span>
                    <span v-if="profile.profession" class="profile-meta-pill">{{ profile.profession }}</span>
                  </div>

                  <p class="profile-persona">{{ profile.persona }}</p>
                  <p class="profile-bio">{{ profile.bio }}</p>

                  <div class="profile-stats">
                    <div class="mini-stat">
                      <span class="mini-label">Followers</span>
                      <span class="mini-value">{{ profile.follower_count ?? 0 }}</span>
                    </div>
                    <div class="mini-stat">
                      <span class="mini-label">Posts/Hr</span>
                      <span class="mini-value">{{ agentConfigById.get(profile.user_id)?.posts_per_hour ?? 'N/A' }}</span>
                    </div>
                    <div class="mini-stat">
                      <span class="mini-label">Comments/Hr</span>
                      <span class="mini-value">{{ agentConfigById.get(profile.user_id)?.comments_per_hour ?? 'N/A' }}</span>
                    </div>
                    <div class="mini-stat">
                      <span class="mini-label">Influence</span>
                      <span class="mini-value">{{ agentConfigById.get(profile.user_id)?.influence_weight ?? 'N/A' }}</span>
                    </div>
                  </div>

                  <div class="profile-foot">
                    <span v-if="profile.age" class="info-chip">{{ profile.age }} yrs</span>
                    <span v-if="profile.country" class="info-chip">{{ profile.country }}</span>
                    <span v-if="profile.gender" class="info-chip">{{ profile.gender }}</span>
                    <span v-if="profile.source_entity_uuid" class="info-chip mono">
                      {{ shortenUuid(profile.source_entity_uuid) }}
                    </span>
                  </div>

                  <div v-if="profile.interested_topics?.length" class="tag-row compact">
                    <span v-for="topic in profile.interested_topics.slice(0, 6)" :key="topic" class="entity-tag soft-tag">
                      {{ topic }}
                    </span>
                  </div>
                </article>
              </div>

            </template>

            <div v-if="!simulationProfiles.length" class="empty-state">
              <div class="empty-mark">02</div>
              <p>
                {{ simulationConfig ? 'No profiles were returned for this simulation, but runtime actions can still be reviewed below.' : 'Run Simulation Prepare to generate personas and reviewable config for this project.' }}
              </p>
            </div>

            <div v-if="simulationConfig" class="runtime-feed-panel">
              <div class="runtime-feed-head">
                <div>
                  <span class="panel-title">ACTION STREAM</span>
                  <p class="description">
                    Recent Twitter / Reddit actions from the Step 3 runtime. Latest items appear first.
                  </p>
                </div>
                <div class="feed-tabs">
                  <button
                    v-for="platform in actionPlatformTabs"
                    :key="platform.value"
                    class="filter-chip"
                    :class="{ active: runtimeActionPlatform === platform.value }"
                    :disabled="actionsLoading"
                    @click="setRuntimeActionPlatform(platform.value)"
                  >
                    {{ platform.label }}
                  </button>
                </div>
              </div>

              <div class="runtime-feed-stats">
                <div class="mini-stat">
                  <span class="mini-label">Runtime</span>
                  <span class="mini-value">{{ runtimeStatusMeta.label }}</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-label">Round</span>
                  <span class="mini-value">{{ runtimeRoundText }}</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-label">Twitter</span>
                  <span class="mini-value">{{ runtimeStatus?.twitter_actions_count ?? 0 }}</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-label">Reddit</span>
                  <span class="mini-value">{{ runtimeStatus?.reddit_actions_count ?? 0 }}</span>
                </div>
              </div>

              <div v-if="runtimeError" class="inline-error">
                {{ summarizeError(runtimeError) }}
              </div>

              <div v-if="displayedRuntimeActions.length" class="action-feed">
                <article
                  v-for="(action, index) in displayedRuntimeActions"
                  :key="actionKey(action, index)"
                  class="action-item"
                  :class="action.platform"
                >
                  <div class="action-meta">
                    <span class="badge soft">{{ action.platform || 'unknown' }}</span>
                    <span class="mono">round {{ action.round_number ?? 'N/A' }}</span>
                    <span class="mono">agent {{ action.agent_id ?? 'N/A' }}</span>
                    <span>{{ formatActionTime(action.created_at) }}</span>
                  </div>
                  <div class="action-title">
                    <span>{{ action.agent_name || `Agent ${action.agent_id ?? '?'}` }}</span>
                    <span class="action-type">{{ normalizeActionType(action.action_type) }}</span>
                  </div>
                  <p class="action-content">{{ action.content || action.topic || 'No action content.' }}</p>
                  <div v-if="action.topic" class="tag-row compact">
                    <span class="entity-tag soft-tag">{{ action.topic }}</span>
                  </div>
                </article>
              </div>

              <div v-else class="empty-module-state">
                {{ actionsLoading ? 'Loading action log...' : 'No runtime actions yet. Start the simulation to stream activity.' }}
              </div>
            </div>
          </div>
        </section>

        <section class="panel-shell workbench-shell">
          <div class="scroll-container">
            <div class="step-card create-card active">
              <div class="card-header">
                <div class="step-info">
                  <span class="step-num">00</span>
                  <span class="step-title">Task Module</span>
                </div>
                <div class="step-status">
                  <span class="badge accent">Workspace</span>
                </div>
              </div>

              <div class="card-content">
                <p class="api-note">Reference: MiroFish Step 2 confirmation surface</p>
                <p class="description">
                  Select the graph-ready project, restore by <span class="mono">project_id</span> or
                  <span class="mono">simulation_id</span>, then review prepare outputs in a stable Step 2 layout.
                </p>

                <div v-if="projects.length" class="project-grid">
                  <button
                    v-for="project in projects"
                    :key="project.id"
                    class="project-card-button"
                    :class="{ active: selectedProjectId === project.id }"
                    @click="selectProject(project.id)"
                  >
                    <div class="project-card-top">
                      <span class="project-card-name">{{ project.name }}</span>
                      <span :class="statusMeta(project.status).class">{{ statusMeta(project.status).label }}</span>
                    </div>
                    <div class="project-card-desc">
                      {{ project.simulation_requirement || 'No simulation requirement.' }}
                    </div>
                    <div class="project-card-id mono">{{ project.id }}</div>
                  </button>
                </div>

                <div v-else class="empty-module-state">
                  No projects yet. Go back to Step 1 to create one first.
                </div>
              </div>
            </div>

            <div class="step-card" :class="{ active: prepareTask?.status === 'processing', completed: simulationConfig }">
              <div class="card-header">
                <div class="step-info">
                  <span class="step-num">04</span>
                  <span class="step-title">Simulation Prepare</span>
                </div>
                <div class="step-status">
                  <span v-if="simulationConfig" class="badge success">Completed</span>
                  <span v-else-if="prepareTask?.status === 'processing'" class="badge processing">
                    {{ prepareTask.progress }}%
                  </span>
                  <span v-else class="badge pending">Pending</span>
                </div>
              </div>

              <div class="card-content">
                <p class="api-note">
                  POST /api/simulation/prepare/{project_id} · GET /api/simulation/prepare/status/{task_id}
                </p>
                <p class="description">
                  Build agent personas and simulation config from cached graph entities. MiroFish Step 2 uses this
                  stage as the handoff from graph understanding to runnable environment review.
                </p>

                <div class="info-grid">
                  <div class="info-item">
                    <span class="info-label">Project</span>
                    <span class="info-value">{{ selectedProject?.name || 'None selected' }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">Graph ID</span>
                    <span class="info-value mono">{{ selectedProject?.zep_graph_id || 'N/A' }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">Nodes</span>
                    <span class="info-value">{{ graphData?.node_count || 0 }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">Edges</span>
                    <span class="info-value">{{ graphData?.edge_count || 0 }}</span>
                  </div>
                  <div class="info-item full">
                    <span class="info-label">Requirement</span>
                    <span class="info-value">{{ selectedProject?.simulation_requirement || 'Select a project first.' }}</span>
                  </div>
                </div>

                <div class="budget-grid">
                  <label class="budget-card">
                    <span class="tag-label">TOTAL ROUNDS</span>
                    <input
                      v-model="prepareForm.total_rounds"
                      class="input-field"
                      type="number"
                      min="1"
                      max="240"
                      inputmode="numeric"
                      placeholder="Auto from config"
                    />
                    <p>Leave blank to keep the generated default. Lower values finish faster.</p>
                  </label>

                  <label class="budget-card">
                    <span class="tag-label">ACTIVE AGENT CAP</span>
                    <input
                      v-model="prepareForm.active_agent_cap"
                      class="input-field"
                      type="number"
                      min="1"
                      inputmode="numeric"
                      placeholder="Auto upper bound"
                    />
                    <p>Optional upper bound per round. Lower caps reduce LLM calls and stop latency.</p>
                  </label>
                </div>

                <div class="tag-section">
                  <div class="tag-header">
                    <span class="tag-label">ENTITY TYPE FILTER</span>
                    <button class="link-btn" :disabled="selectedEntityTypes.length === 0" @click="clearEntityTypeFilters">
                      Use All Types
                    </button>
                  </div>
                  <div class="tag-row">
                    <button
                      v-for="entityType in entityTypeOptions"
                      :key="entityType"
                      class="filter-chip"
                      :class="{ active: selectedEntityTypes.includes(entityType) }"
                      @click="toggleEntityType(entityType)"
                    >
                      {{ entityType }}
                    </button>
                  </div>
                </div>

                <div class="toggle-grid">
                  <label class="toggle-card">
                    <input v-model="prepareForm.twitter_enabled" type="checkbox" />
                    <div>
                      <span class="toggle-title">Twitter</span>
                      <p>Include Twitter runtime config and actions.</p>
                    </div>
                  </label>
                  <label class="toggle-card">
                    <input v-model="prepareForm.reddit_enabled" type="checkbox" />
                    <div>
                      <span class="toggle-title">Reddit</span>
                      <p>Include Reddit runtime config and actions.</p>
                    </div>
                  </label>
                  <label class="toggle-card">
                    <input v-model="prepareForm.use_llm_for_profiles" type="checkbox" />
                    <div>
                      <span class="toggle-title">LLM Profiles</span>
                      <p>Refine persona text with the model when available.</p>
                    </div>
                  </label>
                  <label class="toggle-card">
                    <input v-model="prepareForm.use_llm_for_config" type="checkbox" />
                    <div>
                      <span class="toggle-title">LLM Config</span>
                      <p>Refine schedule and event defaults with the model.</p>
                    </div>
                  </label>
                </div>

                <div v-if="prepareTask" class="progress-section">
                  <div class="spinner-sm" v-if="prepareTask.status === 'processing'"></div>
                  <span>{{ prepareTask.message || 'Preparing simulation...' }}</span>
                  <span class="progress-number">{{ prepareTask.progress }}%</span>
                </div>

                <div v-if="prepareError || prepareTask?.error" class="inline-error">
                  {{ summarizeError(prepareError || prepareTask?.error || '') }}
                </div>

                <div class="action-row">
                  <button class="action-btn secondary" :disabled="!selectedProject" @click="goToGraph">
                    Return To Step 1
                  </button>
                  <button
                    class="action-btn"
                    :disabled="prepareSubmitting || !selectedProject?.zep_graph_id"
                    @click="startPrepare"
                  >
                    <span v-if="prepareSubmitting" class="spinner-sm"></span>
                    {{ prepareSubmitting ? 'Preparing...' : 'Run Prepare' }}
                  </button>
                </div>
              </div>
            </div>

            <div class="step-card" :class="{ active: !!simulationConfig, completed: !!simulationConfig }">
              <div class="card-header">
                <div class="step-info">
                  <span class="step-num">05</span>
                  <span class="step-title">Review Config</span>
                </div>
                <div class="step-status">
                  <span v-if="simulationConfig" class="badge accent">Ready</span>
                  <span v-else class="badge pending">Waiting</span>
                </div>
              </div>

              <div class="card-content">
                <p class="api-note">
                  GET /api/simulation/{simulation_id}/profiles · GET /api/simulation/{simulation_id}/config
                </p>
                <p class="description">
                  Review agent roster, platform toggles, time settings, and event seeds before moving into runtime
                  orchestration.
                </p>

                <template v-if="simulationConfig">
                  <div class="info-grid">
                    <div class="info-item">
                      <span class="info-label">Simulation ID</span>
                      <span class="info-value mono">{{ simulationConfig.simulation_id }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Generated</span>
                      <span class="info-value">{{ formatTimestamp(simulationConfig.generated_at) }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Target Rounds</span>
                      <span class="info-value">{{ runtimeStatus?.total_rounds || totalRounds }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Active Cap</span>
                      <span class="info-value">{{ simulationConfig.time_config.active_agent_cap ?? 'Auto' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Hours</span>
                      <span class="info-value">{{ simulationConfig.time_config.total_simulation_hours }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Round Minutes</span>
                      <span class="info-value">{{ simulationConfig.time_config.minutes_per_round }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Agents / Hr</span>
                      <span class="info-value">
                        {{ simulationConfig.time_config.agents_per_hour_min }} - {{ simulationConfig.time_config.agents_per_hour_max }}
                      </span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Reasoning</span>
                      <span class="info-value">{{ simulationConfig.generation_reasoning }}</span>
                    </div>
                  </div>

                  <div class="config-block">
                    <span class="tag-label">PLATFORMS</span>
                    <div class="platform-grid">
                      <div v-for="platform in platformCards" :key="platform.platform" class="platform-card">
                        <div class="platform-head">
                          <span>{{ platform.platform.toUpperCase() }}</span>
                          <span class="badge success">Enabled</span>
                        </div>
                        <div class="platform-metrics">
                          <span>Recency {{ platform.recency_weight }}</span>
                          <span>Popularity {{ platform.popularity_weight }}</span>
                          <span>Relevance {{ platform.relevance_weight }}</span>
                          <span>Viral {{ platform.viral_threshold }}</span>
                        </div>
                        <div class="tag-row compact">
                          <span v-for="action in platform.available_actions" :key="action" class="entity-tag soft-tag">
                            {{ action }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="config-block" v-if="simulationConfig.event_config.hot_topics.length">
                    <span class="tag-label">EVENT SEEDS</span>
                    <div class="tag-row compact">
                      <span
                        v-for="topic in simulationConfig.event_config.hot_topics"
                        :key="topic"
                        class="entity-tag"
                      >
                        {{ topic }}
                      </span>
                    </div>
                    <p class="narrative-text">{{ simulationConfig.event_config.narrative_direction }}</p>
                  </div>

                  <div class="event-grid">
                    <div class="event-card">
                      <span class="event-title">Initial Posts</span>
                      <div v-if="simulationConfig.event_config.initial_posts.length" class="event-list">
                        <div
                          v-for="(post, index) in simulationConfig.event_config.initial_posts"
                          :key="`${post.poster_agent_id}-${index}`"
                          class="event-item"
                        >
                          <span class="mono">agent {{ post.poster_agent_id }}</span>
                          <span>{{ post.content }}</span>
                        </div>
                      </div>
                      <div v-else class="event-empty">No seeded posts.</div>
                    </div>

                    <div class="event-card">
                      <span class="event-title">Scheduled Events</span>
                      <div v-if="simulationConfig.event_config.scheduled_events.length" class="event-list">
                        <div
                          v-for="(event, index) in simulationConfig.event_config.scheduled_events"
                          :key="`${event.round}-${index}`"
                          class="event-item"
                        >
                          <span class="mono">round {{ event.round }}</span>
                          <span>{{ event.description }}</span>
                        </div>
                      </div>
                      <div v-else class="event-empty">No scheduled spikes.</div>
                    </div>
                  </div>
                </template>

                <div v-else class="empty-module-state">
                  Simulation config has not been generated yet.
                </div>
              </div>
            </div>

            <div
              class="step-card runtime-card"
              :class="{ active: !!simulationConfig, completed: runtimeStatus?.interactive_ready }"
            >
              <div class="card-header">
                <div class="step-info">
                  <span class="step-num">06</span>
                  <span class="step-title">Runtime Console</span>
                </div>
                <div class="step-status">
                  <span :class="runtimeStatusMeta.class">{{ runtimeStatusMeta.label }}</span>
                </div>
              </div>

              <div class="card-content">
                <p class="api-note">
                  POST /api/simulation/start/{simulation_id} · GET /api/simulation/status/{simulation_id} · POST /api/simulation/stop/{simulation_id}
                </p>
                <p class="description">
                  Start the Step 3 runtime, poll DB-backed progress, and stop via IPC without making the browser a state writer.
                </p>

                <template v-if="simulationConfig">
                  <div class="runtime-meter">
                    <div>
                      <span class="tag-label">ROUND PROGRESS</span>
                      <div class="runtime-round-text">{{ runtimeRoundText }}</div>
                    </div>
                    <div class="runtime-bar" aria-label="Simulation progress">
                      <span :style="{ width: `${runtimeProgress}%` }"></span>
                    </div>
                  </div>

                  <div class="info-grid">
                    <div class="info-item">
                      <span class="info-label">Simulation</span>
                      <span class="info-value mono">{{ activeSimulationId }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Interactive</span>
                      <span class="info-value">{{ runtimeStatus?.interactive_ready ? 'Ready for Explorer' : 'Not ready' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Twitter Actions</span>
                      <span class="info-value">{{ runtimeStatus?.twitter_actions_count ?? 0 }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Reddit Actions</span>
                      <span class="info-value">{{ runtimeStatus?.reddit_actions_count ?? 0 }}</span>
                    </div>
                  </div>

                  <div v-if="runtimeStatus?.error || runtimeError" class="inline-error">
                    {{ summarizeError(runtimeStatus?.error || runtimeError) }}
                  </div>

                  <div v-if="runtimeStatus?.interactive_ready" class="explorer-ready">
                    <div>
                      <span class="event-title">Explorer handoff is ready</span>
                      <p>Simulation artifacts are ready for Step 4 Explorer ask and interview workflows.</p>
                    </div>
                    <button class="action-btn secondary" @click="goToExplorer">
                      Open Explorer
                    </button>
                  </div>

                  <div class="action-row">
                    <button
                      class="action-btn secondary"
                      :disabled="runtimeLoading || !activeSimulationId"
                      @click="refreshSimulationRuntime"
                    >
                      {{ runtimeLoading ? 'Refreshing...' : 'Refresh Runtime' }}
                    </button>
                    <button
                      class="action-btn"
                      :disabled="runtimeStarting || !canStartRuntime"
                      @click="startSimulationRuntime"
                    >
                      <span v-if="runtimeStarting" class="spinner-sm"></span>
                      {{ startRuntimeLabel }}
                    </button>
                    <button
                      class="action-btn danger-action"
                      :disabled="runtimeStopping || runtimeStatus?.status !== 'running'"
                      @click="stopSimulationRuntime"
                    >
                      <span v-if="runtimeStopping" class="spinner-sm"></span>
                      {{ runtimeStopping ? 'Stopping...' : 'Stop Simulation' }}
                    </button>
                  </div>
                </template>

                <div v-else class="empty-module-state">
                  Generate or restore a simulation config before starting runtime.
                </div>
              </div>
            </div>

            <div class="log-toggle-row">
              <button
                class="log-toggle-btn"
                :class="{ active: showSystemDashboard }"
                :aria-expanded="showSystemDashboard"
                @click="showSystemDashboard = !showSystemDashboard"
              >
                {{ showSystemDashboard ? 'Hide System Dashboard' : `Show System Dashboard (${systemLogs.length})` }}
              </button>
            </div>

            <div v-if="showSystemDashboard" class="system-logs">
              <div class="log-header">
                <span class="log-title">SYSTEM DASHBOARD</span>
                <span class="log-id">{{ selectedProject?.id || 'NO_PROJECT' }}</span>
              </div>
              <div ref="logContentRef" class="log-content">
                <div v-for="(log, index) in systemLogs" :key="index" class="log-line">
                  <span class="log-time">{{ log.time }}</span>
                  <span class="log-msg">{{ log.msg }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  </v-app>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useHead } from 'nuxt/app'
import { useRoute, useRouter } from 'vue-router'
import { getApiErrorMessage, useApiFetch } from '~/composables/useApiFetch'
import { buildGraphRouteQuery } from '~/utils/workspaceRoutes'

type ProjectStatus = 'created' | 'ontology_generated' | 'graph_building' | 'graph_completed' | 'failed'
type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'
type RuntimeStatus = 'created' | 'preparing' | 'ready' | 'running' | 'completed' | 'stopped' | 'failed'
type RuntimeActionPlatform = 'all' | 'twitter' | 'reddit'

type ProjectRecord = {
  id: string
  name: string
  status: ProjectStatus
  zep_graph_id: string | null
  simulation_requirement: string
  ontology_path: string | null
  extracted_text_path: string | null
  created_at: string
  updated_at: string
}

type ProjectListResponse = {
  projects: ProjectRecord[]
}

type TaskRecord = {
  task_id: string
  task_type: string
  project_id: string | null
  simulation_id: string | null
  status: TaskStatus
  progress: number
  message: string
  result_json: Record<string, any> | null
  progress_detail_json: Record<string, any> | null
  error: string | null
  created_at: string
  updated_at: string
}

type TaskResponse = {
  task_id: string
}

type GraphDataNode = {
  uuid: string
  labels: string[]
}

type GraphDataEdge = {
  uuid: string
}

type GraphDataResponse = {
  graph_id: string
  nodes: GraphDataNode[]
  edges: GraphDataEdge[]
  node_count: number
  edge_count: number
}

type SimulationProfile = {
  user_id: number
  username: string
  name: string
  bio: string
  persona: string
  profession?: string | null
  interested_topics?: string[]
  source_entity_uuid?: string | null
  source_entity_type?: string | null
  age?: number | null
  gender?: string | null
  country?: string | null
  karma?: number
  friend_count?: number
  follower_count?: number
  statuses_count?: number
}

type SimulationProfilesResponse = {
  simulation_id: string
  count: number
  profiles: SimulationProfile[]
}

type TimeConfig = {
  total_simulation_hours: number
  minutes_per_round: number
  agents_per_hour_min: number
  agents_per_hour_max: number
  active_agent_cap?: number | null
}

type AgentConfig = {
  agent_id: number
  entity_uuid: string
  entity_name: string
  entity_type: string
  activity_level: number
  posts_per_hour: number
  comments_per_hour: number
  active_hours: number[]
  response_delay_min: number
  response_delay_max: number
  sentiment_bias: number
  stance: string
  influence_weight: number
}

type EventSeed = Record<string, any>

type EventConfig = {
  initial_posts: EventSeed[]
  scheduled_events: EventSeed[]
  hot_topics: string[]
  narrative_direction: string
}

type PlatformConfig = {
  platform: string
  recency_weight: number
  popularity_weight: number
  relevance_weight: number
  viral_threshold: number
  echo_chamber_strength: number
  available_actions: string[]
}

type SimulationConfig = {
  simulation_id: string
  project_id: string
  graph_id: string
  simulation_requirement: string
  time_config: TimeConfig
  agent_configs: AgentConfig[]
  event_config: EventConfig
  twitter_config: PlatformConfig | null
  reddit_config: PlatformConfig | null
  llm_model: string
  llm_base_url: string
  generated_at: string
  generation_reasoning: string
}

type SimulationAction = {
  simulation_id?: string
  platform?: string
  round_number?: number
  agent_id?: number
  agent_name?: string
  action_type?: string
  topic?: string
  content?: string
  created_at?: string
  metadata?: Record<string, any>
}

type SimulationStatusResponse = {
  simulation_id: string
  project_id: string
  status: RuntimeStatus
  total_rounds: number | null
  current_round: number
  twitter_enabled: boolean
  reddit_enabled: boolean
  twitter_actions_count: number
  reddit_actions_count: number
  recent_actions: SimulationAction[]
  interactive_ready: boolean
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

type SimulationActionsResponse = {
  simulation_id: string
  count: number
  actions: SimulationAction[]
}

type StartSimulationResponse = {
  simulation_id: string
  status: RuntimeStatus
  pid: number
}

type StopSimulationResponse = {
  simulation_id: string
  status: string
  command_id: string
}

type PersistedWorkspaceState = {
  selectedProjectId: string | null
  prepareTaskIds: Record<string, string>
  simulationIds: Record<string, string>
}

type SystemLog = {
  time: string
  msg: string
}

const STORAGE_KEY = 'fyp.simulation.workspace.v1'

const apiFetch = useApiFetch()
const route = useRoute()
const router = useRouter()

useHead({
  title: 'Simulation Prepare Workspace',
})

const projects = ref<ProjectRecord[]>([])
const selectedProjectId = ref<string | null>(null)
const graphData = ref<GraphDataResponse | null>(null)
const prepareTask = ref<TaskRecord | null>(null)
const simulationConfig = ref<SimulationConfig | null>(null)
const simulationProfiles = ref<SimulationProfile[]>([])
const runtimeStatus = ref<SimulationStatusResponse | null>(null)
const runtimeActions = ref<SimulationAction[]>([])
const selectedEntityTypes = ref<string[]>([])
const profileSearch = ref('')
const runtimeActionPlatform = ref<RuntimeActionPlatform>('all')
const showSystemDashboard = ref(false)

const projectsLoading = ref(false)
const graphLoading = ref(false)
const prepareSubmitting = ref(false)
const resultsLoading = ref(false)
const runtimeLoading = ref(false)
const runtimeStarting = ref(false)
const runtimeStopping = ref(false)
const actionsLoading = ref(false)

const pageError = ref('')
const prepareError = ref('')
const resultsError = ref('')
const runtimeError = ref('')

const systemLogs = ref<SystemLog[]>([])
const logContentRef = ref<HTMLDivElement | null>(null)
const lastPrepareMessage = ref('')

const prepareForm = reactive({
  use_llm_for_profiles: true,
  use_llm_for_config: true,
  twitter_enabled: true,
  reddit_enabled: true,
  total_rounds: '',
  active_agent_cap: '',
})

const persistedState = reactive<PersistedWorkspaceState>({
  selectedProjectId: null,
  prepareTaskIds: {},
  simulationIds: {},
})

let preparePollTimer: ReturnType<typeof window.setInterval> | null = null
let runtimePollTimer: ReturnType<typeof window.setInterval> | null = null

const selectedProject = computed(() => {
  return projects.value.find((project) => project.id === selectedProjectId.value) || null
})

const activeSimulationId = computed(() => {
  if (simulationConfig.value?.simulation_id) {
    return simulationConfig.value.simulation_id
  }
  if (prepareTask.value?.simulation_id) {
    return prepareTask.value.simulation_id
  }
  if (!selectedProjectId.value) {
    return null
  }
  return persistedState.simulationIds[selectedProjectId.value] || null
})

const entityTypeOptions = computed(() => {
  const labels = (graphData.value?.nodes || []).flatMap((node) => node.labels.filter((label) => !['Entity', 'Node'].includes(label)))
  return Array.from(new Set(labels)).filter(Boolean).sort((a, b) => a.localeCompare(b))
})

const agentConfigById = computed(() => {
  return new Map((simulationConfig.value?.agent_configs || []).map((config) => [config.agent_id, config]))
})

const filteredProfiles = computed(() => {
  const query = profileSearch.value.trim().toLowerCase()
  const activeTypes = new Set(selectedEntityTypes.value)

  return simulationProfiles.value.filter((profile) => {
    const profileType = profile.source_entity_type || ''
    if (activeTypes.size > 0 && !activeTypes.has(profileType)) {
      return false
    }

    if (!query) {
      return true
    }

    const haystack = [
      profile.name,
      profile.username,
      profile.persona,
      profile.bio,
      profile.profession || '',
      profile.source_entity_type || '',
      ...(profile.interested_topics || []),
    ]
      .join(' ')
      .toLowerCase()

    return haystack.includes(query)
  })
})

const platformCards = computed(() => {
  return [simulationConfig.value?.twitter_config, simulationConfig.value?.reddit_config].filter(
    (platform): platform is PlatformConfig => platform !== null && platform !== undefined,
  )
})

const hotTopics = computed(() => simulationConfig.value?.event_config.hot_topics || [])

const totalRounds = computed(() => {
  const runtimeRounds = runtimeStatus.value?.total_rounds
  if (runtimeRounds && runtimeRounds > 0) {
    return runtimeRounds
  }
  const timeConfig = simulationConfig.value?.time_config
  if (!timeConfig) {
    return 0
  }
  return Math.max(1, Math.ceil((timeConfig.total_simulation_hours * 60) / Math.max(timeConfig.minutes_per_round, 1)))
})

const totalRuntimeActions = computed(() => {
  return (runtimeStatus.value?.twitter_actions_count || 0) + (runtimeStatus.value?.reddit_actions_count || 0)
})

const runtimeStatusMeta = computed(() => runtimeMeta(runtimeStatus.value?.status || (simulationConfig.value ? 'ready' : 'created')))

const runtimeRoundText = computed(() => {
  const currentRound = runtimeStatus.value?.current_round ?? 0
  const total = runtimeStatus.value?.total_rounds || totalRounds.value || 0
  return total ? `${currentRound} / ${total}` : `${currentRound}`
})

const runtimeProgress = computed(() => {
  const currentRound = runtimeStatus.value?.current_round ?? 0
  const total = runtimeStatus.value?.total_rounds || totalRounds.value || 0
  if (total <= 0) {
    return 0
  }
  return Math.min(100, Math.max(0, Math.round((currentRound / total) * 100)))
})

const displayedRuntimeActions = computed(() => {
  const source = runtimeActions.value.length ? runtimeActions.value : runtimeStatus.value?.recent_actions || []
  return [...source].reverse()
})

const canStartRuntime = computed(() => {
  if (!activeSimulationId.value || !simulationConfig.value) {
    return false
  }
  const status = runtimeStatus.value?.status || 'ready'
  return ['ready', 'completed', 'stopped', 'failed'].includes(status)
})

const startRuntimeLabel = computed(() => {
  if (runtimeStarting.value) {
    return 'Starting...'
  }
  if (runtimeStatus.value?.status === 'completed' || runtimeStatus.value?.status === 'stopped') {
    return 'Restart Simulation'
  }
  return 'Start Simulation'
})

const actionPlatformTabs: Array<{ label: string; value: RuntimeActionPlatform }> = [
  { label: 'All', value: 'all' },
  { label: 'Twitter', value: 'twitter' },
  { label: 'Reddit', value: 'reddit' },
]

const latestError = computed(() => {
  return pageError.value || prepareError.value || resultsError.value || runtimeError.value || prepareTask.value?.error || ''
})

const statusClass = computed(() => {
  if (latestError.value) {
    return 'error'
  }
  if (runtimeStatus.value?.status === 'running') {
    return 'processing'
  }
  if (runtimeStatus.value?.interactive_ready) {
    return 'completed'
  }
  if (simulationConfig.value) {
    return 'completed'
  }
  if (prepareTask.value?.status === 'processing' || prepareTask.value?.status === 'pending') {
    return 'processing'
  }
  if (selectedProject.value) {
    return 'idle'
  }
  return 'idle'
})

const statusText = computed(() => {
  if (latestError.value) {
    return 'Error'
  }
  if (runtimeStatus.value?.status === 'running') {
    return 'Simulation Running'
  }
  if (runtimeStatus.value?.interactive_ready) {
    return 'Explorer Ready'
  }
  if (simulationConfig.value) {
    return 'Review Ready'
  }
  if (prepareTask.value?.status === 'processing' || prepareTask.value?.status === 'pending') {
    return 'Preparing Agents'
  }
  if (selectedProject.value) {
    return 'Ready'
  }
  return 'Idle'
})

function addLog(msg: string) {
  const now = new Date()
  const time =
    now.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }) +
    '.' +
    now.getMilliseconds().toString().padStart(3, '0')

  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 120) {
    systemLogs.value.shift()
  }
}

function summarizeError(error: string | null | undefined) {
  if (!error) {
    return ''
  }
  return error.split('\n').slice(0, 3).join('\n')
}

function normalizeApiError(error: unknown) {
  const message = getApiErrorMessage(error)
  return message
}

function formatTimestamp(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('en-US', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function shortenUuid(value: string) {
  return value.length <= 14 ? value : `${value.slice(0, 6)}...${value.slice(-4)}`
}

function statusMeta(status: ProjectStatus) {
  const meta: Record<ProjectStatus, { label: string; class: string }> = {
    created: { label: 'Created', class: 'badge pending' },
    ontology_generated: { label: 'Ontology Ready', class: 'badge success' },
    graph_building: { label: 'Building', class: 'badge processing' },
    graph_completed: { label: 'Graph Ready', class: 'badge accent' },
    failed: { label: 'Failed', class: 'badge danger' },
  }
  return meta[status] ?? { label: status, class: 'badge pending' }
}

function runtimeMeta(status: RuntimeStatus | string) {
  const meta: Record<string, { label: string; class: string }> = {
    created: { label: 'Not Prepared', class: 'badge pending' },
    preparing: { label: 'Preparing', class: 'badge processing' },
    ready: { label: 'Ready', class: 'badge accent' },
    running: { label: 'Running', class: 'badge processing' },
    completed: { label: 'Completed', class: 'badge success' },
    stopped: { label: 'Stopped', class: 'badge success' },
    failed: { label: 'Failed', class: 'badge danger' },
  }
  return meta[status] ?? { label: status, class: 'badge pending' }
}

function normalizeActionType(value: string | undefined) {
  return value ? value.replaceAll('_', ' ') : 'ACTION'
}

function formatActionTime(value: string | undefined) {
  if (!value) {
    return 'pending'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function actionKey(action: SimulationAction, index: number) {
  return [
    action.platform || 'platform',
    action.round_number ?? 'round',
    action.agent_id ?? 'agent',
    action.action_type || 'action',
    action.created_at || index,
  ].join(':')
}

function parseOptionalPositiveInt(value: string, label: string) {
  const normalized = value.trim()
  if (!normalized) {
    return null
  }
  const parsed = Number.parseInt(normalized, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${label} must be a positive integer.`)
  }
  return parsed
}

function persistWorkspaceState() {
  if (!import.meta.client) {
    return
  }

  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      selectedProjectId: selectedProjectId.value,
      prepareTaskIds: persistedState.prepareTaskIds,
      simulationIds: persistedState.simulationIds,
    }),
  )
}

function loadWorkspaceState() {
  if (!import.meta.client) {
    return
  }

  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return
  }

  try {
    const parsed = JSON.parse(raw) as PersistedWorkspaceState
    persistedState.selectedProjectId = parsed.selectedProjectId || null
    persistedState.prepareTaskIds = parsed.prepareTaskIds || {}
    persistedState.simulationIds = parsed.simulationIds || {}
  } catch {
    window.localStorage.removeItem(STORAGE_KEY)
  }
}

function syncProjectQuery(projectId: string | null) {
  const currentProjectId = typeof route.query.project === 'string' ? route.query.project : null
  if (currentProjectId === projectId) {
    return
  }

  const nextQuery = { ...route.query }
  if (projectId) {
    nextQuery.project = projectId
  } else {
    delete nextQuery.project
  }

  void router.replace({ query: nextQuery })
}

function syncSimulationQuery(simulationId: string | null) {
  const currentSimulationId = typeof route.query.simulation === 'string' ? route.query.simulation : null
  if (currentSimulationId === simulationId) {
    return
  }

  const nextQuery = { ...route.query }
  if (simulationId) {
    nextQuery.simulation = simulationId
  } else {
    delete nextQuery.simulation
  }

  void router.replace({ query: nextQuery })
}

function stopPreparePolling() {
  if (preparePollTimer) {
    clearInterval(preparePollTimer)
    preparePollTimer = null
  }
}

function stopRuntimePolling() {
  if (runtimePollTimer) {
    clearInterval(runtimePollTimer)
    runtimePollTimer = null
  }
}

function clearRuntimeState() {
  stopRuntimePolling()
  runtimeStatus.value = null
  runtimeActions.value = []
  runtimeError.value = ''
  runtimeLoading.value = false
  runtimeStarting.value = false
  runtimeStopping.value = false
  actionsLoading.value = false
  runtimeActionPlatform.value = 'all'
}

function clearSimulationResults() {
  simulationConfig.value = null
  simulationProfiles.value = []
  resultsError.value = ''
  resultsLoading.value = false
  profileSearch.value = ''
  clearRuntimeState()
}

async function fetchProjects() {
  projectsLoading.value = true
  try {
    const response = await apiFetch<ProjectListResponse>('/api/graph/projects', { method: 'GET' })
    projects.value = response.projects
  } finally {
    projectsLoading.value = false
  }
}

function resolveInitialProjectId(nextProjects: ProjectRecord[]) {
  const routeProjectId = typeof route.query.project === 'string' ? route.query.project : null
  const candidates = [routeProjectId, selectedProjectId.value, persistedState.selectedProjectId]

  for (const candidate of candidates) {
    if (candidate && nextProjects.some((project) => project.id === candidate)) {
      return candidate
    }
  }

  return nextProjects[0]?.id || null
}

async function fetchPrepareTask(taskId: string) {
  return await apiFetch<TaskRecord>(`/api/simulation/prepare/status/${taskId}`, { method: 'GET' })
}

async function fetchSimulationConfigById(simulationId: string) {
  return await apiFetch<SimulationConfig>(`/api/simulation/${simulationId}/config`, { method: 'GET' })
}

async function fetchSimulationProfilesById(simulationId: string) {
  return await apiFetch<SimulationProfilesResponse>(`/api/simulation/${simulationId}/profiles`, { method: 'GET' })
}

async function fetchSimulationStatusById(simulationId: string, recentLimit = 30) {
  return await apiFetch<SimulationStatusResponse>(`/api/simulation/status/${simulationId}?recent_limit=${recentLimit}`, {
    method: 'GET',
  })
}

async function fetchSimulationActionsById(simulationId: string, platform: RuntimeActionPlatform) {
  const query = platform === 'all' ? '' : `?platform=${platform}`
  return await apiFetch<SimulationActionsResponse>(`/api/simulation/actions/${simulationId}${query}`, { method: 'GET' })
}

async function postSimulationStart(simulationId: string) {
  return await apiFetch<StartSimulationResponse>(`/api/simulation/start/${simulationId}`, { method: 'POST' })
}

async function postSimulationStop(simulationId: string) {
  return await apiFetch<StopSimulationResponse>(`/api/simulation/stop/${simulationId}`, { method: 'POST' })
}

async function resolveProjectIdFromSimulationQuery() {
  const simulationId = typeof route.query.simulation === 'string' ? route.query.simulation : null
  if (!simulationId) {
    return null
  }

  try {
    const config = await fetchSimulationConfigById(simulationId)
    persistedState.simulationIds[config.project_id] = simulationId
    persistWorkspaceState()
    addLog(`Restoring from simulation query: ${simulationId}`)
    return config.project_id
  } catch (error) {
    pageError.value = normalizeApiError(error)
    addLog(`Simulation restore failed: ${pageError.value}`)
    return null
  }
}

async function refreshProjects(preferredProjectId?: string | null) {
  pageError.value = ''
  try {
    await fetchProjects()
    addLog(`Project list refreshed. Count: ${projects.value.length}`)
    const nextProjectId =
      preferredProjectId && projects.value.some((project) => project.id === preferredProjectId)
        ? preferredProjectId
        : resolveInitialProjectId(projects.value)
    await selectProject(nextProjectId)
  } catch (error) {
    pageError.value = normalizeApiError(error)
    addLog(`Error refreshing projects: ${pageError.value}`)
  }
}

async function loadGraphSummary(projectId: string, graphId: string) {
  graphLoading.value = true
  try {
    const response = await apiFetch<GraphDataResponse>(`/api/graph/data/${graphId}`, { method: 'GET' })
    if (selectedProjectId.value !== projectId) {
      return
    }
    graphData.value = response
    addLog(`Graph snapshot loaded. Nodes: ${response.node_count}, Edges: ${response.edge_count}`)
  } catch (error) {
    if (selectedProjectId.value === projectId) {
      pageError.value = normalizeApiError(error)
      graphData.value = null
    }
    addLog(`Graph snapshot failed: ${normalizeApiError(error)}`)
  } finally {
    if (selectedProjectId.value === projectId) {
      graphLoading.value = false
    }
  }
}

async function loadGraphSummaryForProject(projectId: string) {
  const project = projects.value.find((item) => item.id === projectId) || null
  if (!project?.zep_graph_id) {
    graphData.value = null
    return
  }
  await loadGraphSummary(projectId, project.zep_graph_id)
}

async function loadSimulationArtifacts(simulationId: string, projectId: string) {
  resultsLoading.value = true
  resultsError.value = ''

  try {
    const [config, profilesResponse] = await Promise.all([
      fetchSimulationConfigById(simulationId),
      fetchSimulationProfilesById(simulationId),
    ])

    if (selectedProjectId.value !== projectId) {
      return
    }

    simulationConfig.value = config
    simulationProfiles.value = profilesResponse.profiles
    persistedState.simulationIds[projectId] = simulationId
    persistWorkspaceState()
    syncSimulationQuery(simulationId)
    addLog(`Simulation results restored: ${simulationId}`)
    await refreshSimulationRuntimeFor(simulationId, projectId, { loadActions: true })
  } catch (error) {
    if (selectedProjectId.value === projectId) {
      resultsError.value = normalizeApiError(error)
      simulationConfig.value = null
      simulationProfiles.value = []
    }
    addLog(`Simulation result load failed: ${normalizeApiError(error)}`)
  } finally {
    if (selectedProjectId.value === projectId) {
      resultsLoading.value = false
    }
  }
}

async function loadRuntimeActionsFor(simulationId: string, projectId: string) {
  actionsLoading.value = true
  try {
    const response = await fetchSimulationActionsById(simulationId, runtimeActionPlatform.value)
    if (selectedProjectId.value !== projectId || activeSimulationId.value !== simulationId) {
      return
    }
    runtimeActions.value = response.actions
  } catch (error) {
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      runtimeError.value = normalizeApiError(error)
    }
    addLog(`Action log refresh failed: ${normalizeApiError(error)}`)
  } finally {
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      actionsLoading.value = false
    }
  }
}

async function refreshSimulationRuntimeFor(
  simulationId: string,
  projectId: string,
  options: { loadActions?: boolean; silent?: boolean } = {},
) {
  runtimeLoading.value = !options.silent
  runtimeError.value = ''

  try {
    const response = await fetchSimulationStatusById(simulationId)
    if (selectedProjectId.value !== projectId || activeSimulationId.value !== simulationId) {
      return
    }

    runtimeStatus.value = response
    if (!options.silent) {
      addLog(`Runtime status: ${response.status}, round ${response.current_round}`)
    }

    if (response.status === 'running') {
      startRuntimePolling(simulationId, projectId)
    } else {
      stopRuntimePolling()
    }

    if (options.loadActions || response.status !== 'running') {
      await loadRuntimeActionsFor(simulationId, projectId)
    } else if (!runtimeActions.value.length && response.recent_actions.length) {
      runtimeActions.value = response.recent_actions
    }
  } catch (error) {
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      runtimeError.value = normalizeApiError(error)
    }
    addLog(`Runtime status refresh failed: ${normalizeApiError(error)}`)
  } finally {
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      runtimeLoading.value = false
    }
  }
}

async function pollRuntimeStatus(simulationId: string, projectId: string) {
  try {
    const response = await fetchSimulationStatusById(simulationId)
    if (selectedProjectId.value !== projectId || activeSimulationId.value !== simulationId) {
      return
    }

    const previousStatus = runtimeStatus.value?.status
    runtimeStatus.value = response
    if (response.recent_actions.length && runtimeActionPlatform.value === 'all') {
      runtimeActions.value = response.recent_actions
    }

    if (previousStatus !== response.status) {
      addLog(`Runtime state changed: ${response.status}`)
    }

    if (response.status !== 'running') {
      stopRuntimePolling()
      await loadRuntimeActionsFor(simulationId, projectId)
    }
  } catch (error) {
    stopRuntimePolling()
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      runtimeError.value = normalizeApiError(error)
    }
    addLog(`Runtime polling failed: ${normalizeApiError(error)}`)
  }
}

function startRuntimePolling(simulationId: string, projectId: string) {
  if (!import.meta.client) {
    return
  }

  if (runtimePollTimer) {
    return
  }
  runtimePollTimer = window.setInterval(() => {
    void pollRuntimeStatus(simulationId, projectId)
  }, 2000)
}

async function refreshSimulationRuntime() {
  const projectId = selectedProjectId.value
  const simulationId = activeSimulationId.value

  if (!projectId || !simulationId) {
    runtimeError.value = 'No simulation runtime available yet.'
    return
  }
  await refreshSimulationRuntimeFor(simulationId, projectId, { loadActions: true })
}

async function startSimulationRuntime() {
  runtimeError.value = ''
  const projectId = selectedProjectId.value
  const simulationId = activeSimulationId.value

  if (!projectId || !simulationId) {
    runtimeError.value = 'Prepare a simulation before starting runtime.'
    return
  }

  runtimeStarting.value = true
  addLog(`Starting simulation runtime: ${simulationId}`)

  try {
    const response = await postSimulationStart(simulationId)
    addLog(`Runtime process accepted: pid ${response.pid}`)
    await refreshSimulationRuntimeFor(response.simulation_id, projectId, { loadActions: true })
    startRuntimePolling(response.simulation_id, projectId)
  } catch (error) {
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      runtimeError.value = normalizeApiError(error)
      addLog(`Runtime start failed: ${runtimeError.value}`)
    }
  } finally {
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      runtimeStarting.value = false
    }
  }
}

async function stopSimulationRuntime() {
  runtimeError.value = ''
  const projectId = selectedProjectId.value
  const simulationId = activeSimulationId.value

  if (!projectId || !simulationId) {
    runtimeError.value = 'No simulation runtime is selected.'
    return
  }

  runtimeStopping.value = true
  addLog(`Requesting simulation stop: ${simulationId}`)

  try {
    const response = await postSimulationStop(simulationId)
    addLog(`Stop command accepted: ${response.command_id}`)
    startRuntimePolling(response.simulation_id, projectId)
    await pollRuntimeStatus(response.simulation_id, projectId)
  } catch (error) {
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      runtimeError.value = normalizeApiError(error)
      addLog(`Runtime stop failed: ${runtimeError.value}`)
    }
  } finally {
    if (selectedProjectId.value === projectId && activeSimulationId.value === simulationId) {
      runtimeStopping.value = false
    }
  }
}

function setRuntimeActionPlatform(platform: RuntimeActionPlatform) {
  runtimeActionPlatform.value = platform
  const projectId = selectedProjectId.value
  const simulationId = activeSimulationId.value
  if (projectId && simulationId) {
    void loadRuntimeActionsFor(simulationId, projectId)
  }
}

async function pollPrepareTask(taskId: string, projectId: string) {
  try {
    const task = await fetchPrepareTask(taskId)
    if (selectedProjectId.value !== projectId) {
      return
    }

    const changed = task.message && task.message !== lastPrepareMessage.value
    prepareTask.value = task
    if (changed) {
      lastPrepareMessage.value = task.message
      addLog(task.message)
    }

    if (task.status === 'completed' || task.status === 'failed') {
      stopPreparePolling()

      if (task.status === 'failed') {
        addLog('Simulation prepare failed.')
        return
      }

      const simulationId =
        task.simulation_id ||
        (task.result_json && typeof task.result_json === 'object' ? String(task.result_json.simulation_id || '') : '')

      if (simulationId) {
        persistedState.simulationIds[projectId] = simulationId
        persistWorkspaceState()
        await loadSimulationArtifacts(simulationId, projectId)
      }

      addLog('Simulation prepare completed.')
    }
  } catch (error) {
    stopPreparePolling()
    if (selectedProjectId.value === projectId) {
      prepareError.value = normalizeApiError(error)
    }
    addLog(`Prepare polling failed: ${normalizeApiError(error)}`)
  }
}

function startPreparePolling(taskId: string, projectId: string) {
  if (!import.meta.client) {
    return
  }

  stopPreparePolling()
  void pollPrepareTask(taskId, projectId)
  preparePollTimer = window.setInterval(() => {
    void pollPrepareTask(taskId, projectId)
  }, 2500)
}

async function resumePrepareTracking(projectId: string) {
  prepareTask.value = null
  lastPrepareMessage.value = ''

  const prepareTaskId = persistedState.prepareTaskIds[projectId]
  const simulationId = persistedState.simulationIds[projectId]

  if (prepareTaskId) {
    try {
      const task = await fetchPrepareTask(prepareTaskId)
      if (selectedProjectId.value === projectId) {
        prepareTask.value = task
      }
      if (task.message) {
        lastPrepareMessage.value = task.message
      }

      const resolvedSimulationId =
        task.simulation_id ||
        (task.result_json && typeof task.result_json === 'object' ? String(task.result_json.simulation_id || '') : '')

      if (resolvedSimulationId) {
        persistedState.simulationIds[projectId] = resolvedSimulationId
        persistWorkspaceState()
      }

      if (task.status === 'processing' || task.status === 'pending') {
        startPreparePolling(prepareTaskId, projectId)
        return
      }

      if (resolvedSimulationId) {
        await loadSimulationArtifacts(resolvedSimulationId, projectId)
        return
      }
    } catch {
      delete persistedState.prepareTaskIds[projectId]
      persistWorkspaceState()
    }
  }

  if (simulationId) {
    await loadSimulationArtifacts(simulationId, projectId)
  } else {
    syncSimulationQuery(null)
  }
}

async function selectProject(projectId: string | null) {
  selectedProjectId.value = projectId
  persistedState.selectedProjectId = projectId
  persistWorkspaceState()
  syncProjectQuery(projectId)

  pageError.value = ''
  prepareError.value = ''
  resultsError.value = ''
  stopPreparePolling()
  clearSimulationResults()

  if (!projectId) {
    graphData.value = null
    prepareTask.value = null
    return
  }

  addLog(`Project selected: ${projectId}`)
  await Promise.all([loadGraphSummaryForProject(projectId), resumePrepareTracking(projectId)])
}

function toggleEntityType(entityType: string) {
  if (selectedEntityTypes.value.includes(entityType)) {
    selectedEntityTypes.value = selectedEntityTypes.value.filter((item) => item !== entityType)
    return
  }
  selectedEntityTypes.value = [...selectedEntityTypes.value, entityType]
}

function clearEntityTypeFilters() {
  selectedEntityTypes.value = []
}

async function startPrepare() {
  prepareError.value = ''

  if (!selectedProject.value) {
    prepareError.value = 'Select a project before preparing simulation.'
    return
  }
  if (!selectedProject.value.zep_graph_id) {
    prepareError.value = 'The selected project does not have a graph yet.'
    return
  }
  if (!prepareForm.twitter_enabled && !prepareForm.reddit_enabled) {
    prepareError.value = 'Enable at least one platform.'
    return
  }

  prepareSubmitting.value = true
  addLog('Starting simulation prepare.')

  try {
    const totalRounds = parseOptionalPositiveInt(prepareForm.total_rounds, 'Total rounds')
    const activeAgentCap = parseOptionalPositiveInt(prepareForm.active_agent_cap, 'Active agent cap')

    const response = await apiFetch<TaskResponse>(`/api/simulation/prepare/${selectedProject.value.id}`, {
      method: 'POST',
      body: {
        entity_types: selectedEntityTypes.value.length ? selectedEntityTypes.value : null,
        use_llm_for_profiles: prepareForm.use_llm_for_profiles,
        use_llm_for_config: prepareForm.use_llm_for_config,
        twitter_enabled: prepareForm.twitter_enabled,
        reddit_enabled: prepareForm.reddit_enabled,
        total_rounds: totalRounds,
        active_agent_cap: activeAgentCap,
      },
    })

    persistedState.prepareTaskIds[selectedProject.value.id] = response.task_id
    delete persistedState.simulationIds[selectedProject.value.id]
    persistWorkspaceState()
    prepareTask.value = null
    clearSimulationResults()
    syncSimulationQuery(null)
    addLog(`Prepare task started: ${response.task_id}`)
    startPreparePolling(response.task_id, selectedProject.value.id)
  } catch (error) {
    prepareError.value = normalizeApiError(error)
    addLog(`Prepare start failed: ${prepareError.value}`)
  } finally {
    prepareSubmitting.value = false
  }
}

async function refreshSimulationResults() {
  if (!selectedProjectId.value || !activeSimulationId.value) {
    resultsError.value = 'No simulation result available yet.'
    return
  }
  await loadSimulationArtifacts(activeSimulationId.value, selectedProjectId.value)
}

function goToGraph() {
  void router.push({ path: '/graph', query: buildGraphRouteQuery(selectedProjectId.value) })
}

function goToExplorer() {
  const query: Record<string, string> = {}
  if (selectedProjectId.value) {
    query.project = selectedProjectId.value
  }
  if (activeSimulationId.value) {
    query.simulation = activeSimulationId.value
  }
  void router.push({ path: '/explorer', query })
}

watch(entityTypeOptions, (nextTypes) => {
  selectedEntityTypes.value = selectedEntityTypes.value.filter((item) => nextTypes.includes(item))
})

watch(
  () => systemLogs.value.length,
  () => {
    nextTick(() => {
      if (logContentRef.value) {
        logContentRef.value.scrollTop = logContentRef.value.scrollHeight
      }
    })
  },
)

onMounted(async () => {
  addLog('Simulation view initialized.')
  loadWorkspaceState()
  const preferredProjectId = await resolveProjectIdFromSimulationQuery()
  await refreshProjects(preferredProjectId)
})

onBeforeUnmount(() => {
  stopPreparePolling()
  stopRuntimePolling()
})
</script>

<style scoped>
.main-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  color: #111;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.app-header {
  height: 60px;
  border-bottom: 1px solid #eaeaea;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 20;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 1px;
  cursor: pointer;
}

.header-btn,
.action-btn,
.tool-btn,
.filter-chip,
.link-btn {
  border: 1px solid #111;
  background: #111;
  color: #fff;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
}

.header-btn.subtle,
.action-btn.secondary,
.tool-btn,
.filter-chip,
.link-btn {
  background: #fff;
  color: #111;
  border-color: #dedede;
}

.filter-chip.active {
  background: #111;
  color: #fff;
  border-color: #111;
}

.action-btn.danger-action {
  background: #c62828;
  border-color: #c62828;
}

.action-btn.danger-action:disabled {
  background: #111;
  border-color: #111;
}

.header-btn:hover,
.action-btn:hover,
.tool-btn:hover,
.filter-chip:hover,
.link-btn:hover {
  opacity: 0.86;
}

.header-btn:disabled,
.action-btn:disabled,
.tool-btn:disabled,
.filter-chip:disabled,
.link-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #ccc;
}

.status-indicator.processing .dot {
  background: #ff6f3d;
  animation: pulse 1s infinite;
}

.status-indicator.completed .dot {
  background: #43a047;
}

.status-indicator.error .dot {
  background: #d32f2f;
}

.page-error-banner {
  padding: 10px 24px;
  background: #fff1f0;
  border-bottom: 1px solid #ffd9d6;
  color: #c62828;
  font-size: 12px;
}

.content-area {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(360px, 0.95fr);
  min-height: 0;
}

.panel-shell {
  min-height: 0;
}

.roster-shell {
  border-right: 1px solid #eaeaea;
  display: flex;
  flex-direction: column;
}

.panel-header {
  height: 62px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eaeaea;
}

.panel-title-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.panel-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.panel-subtitle-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-subtitle {
  font-size: 11px;
  color: #888;
}

.panel-body {
  flex: 1;
  overflow: auto;
  background: linear-gradient(180deg, #fcfcfc 0%, #f5f5f5 100%);
  padding: 18px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-card {
  background: #fff;
  border: 1px solid #ececec;
  border-radius: 14px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.summary-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: #777;
}

.roster-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.search-input,
.input-field {
  width: 100%;
  border: 1px solid #dedede;
  border-radius: 10px;
  background: #fff;
  color: #111;
  padding: 12px 14px;
  font-size: 13px;
  outline: none;
}

.search-input {
  max-width: 420px;
}

.toolbar-badges,
.header-tools,
.action-row,
.tag-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.runtime-feed-panel {
  margin-top: 18px;
  border-top: 1px solid #e6e6e6;
  padding-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.runtime-feed-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.feed-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.runtime-feed-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.action-feed {
  max-height: 540px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 2px;
}

.action-item {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-left: 4px solid #111;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-item.twitter {
  border-left-color: #2f6fed;
}

.action-item.reddit {
  border-left-color: #ef6c2f;
}

.action-meta,
.action-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.action-meta {
  color: #888;
  font-size: 11px;
}

.action-title {
  justify-content: space-between;
  font-size: 14px;
  font-weight: 700;
}

.action-type {
  color: #666;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.action-content {
  margin: 0;
  color: #444;
  font-size: 12px;
  line-height: 1.6;
}

.profile-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 18px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.04);
}

.profile-top,
.profile-meta-row,
.profile-foot,
.project-card-top,
.card-header,
.step-info,
.step-status,
.log-header,
.platform-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.profile-heading h3 {
  margin: 0;
  font-size: 16px;
  line-height: 1.1;
}

.profile-heading p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #888;
}

.agent-pill {
  padding: 6px 10px;
  border-radius: 999px;
  background: #111;
  color: #fff;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
}

.profile-username {
  color: #666;
  font-size: 12px;
}

.profile-meta-pill,
.info-chip {
  padding: 5px 9px;
  border-radius: 999px;
  background: #f3f3f3;
  color: #555;
  font-size: 11px;
}

.profile-persona {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #111;
}

.profile-bio,
.description,
.narrative-text {
  margin: 0;
  font-size: 12px;
  line-height: 1.65;
  color: #666;
}

.profile-stats,
.stats-grid,
.info-grid,
.budget-grid,
.toggle-grid,
.event-grid,
.platform-grid,
.project-grid {
  display: grid;
  gap: 12px;
}

.profile-stats {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.mini-stat,
.info-item,
.toggle-card,
.event-card,
.platform-card,
.project-card-button,
.step-card,
.system-logs {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 16px;
}

.mini-stat {
  padding: 10px 12px;
}

.mini-label {
  display: block;
  font-size: 11px;
  color: #888;
  margin-bottom: 4px;
}

.mini-value {
  font-size: 14px;
  font-weight: 700;
}

.tag-section {
  margin-bottom: 16px;
}

.tag-label {
  display: inline-block;
  margin-bottom: 8px;
  font-size: 11px;
  color: #666;
  letter-spacing: 0.08em;
  font-weight: 700;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-row.compact {
  gap: 6px;
}

.entity-tag {
  background: #f0f4ff;
  color: #2643a1;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 600;
}

.soft-tag {
  background: #f5f5f5;
  color: #555;
}

.workbench-shell {
  background: #fcfcfc;
  min-height: 0;
}

.scroll-container {
  height: 100%;
  overflow: auto;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-card,
.system-logs {
  padding: 18px;
}

.runtime-card {
  background:
    linear-gradient(135deg, rgba(17, 17, 17, 0.035), transparent 42%),
    #fff;
}

.step-card.active,
.project-card-button.active {
  border-color: #111;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.05);
}

.step-card.completed {
  border-color: #9ccc65;
}

.step-info {
  justify-content: flex-start;
}

.step-title {
  font-size: 15px;
  font-weight: 700;
}

.card-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 14px;
}

.runtime-meter {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: #fafafa;
  border: 1px solid #e8e8e8;
}

.runtime-round-text {
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.runtime-bar {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #e7e7e7;
}

.runtime-bar span {
  display: block;
  height: 100%;
  min-width: 2px;
  border-radius: inherit;
  background: linear-gradient(90deg, #111, #ff6f3d);
  transition: width 0.35s ease;
}

.explorer-ready {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  background: #edf8ec;
  border: 1px solid #cfe8cf;
}

.explorer-ready p {
  margin: 4px 0 0;
  color: #4d7d4d;
  font-size: 12px;
  line-height: 1.55;
}

.api-note {
  margin: 0;
  font-size: 11px;
  color: #7d7d7d;
  font-family: 'JetBrains Mono', monospace;
}

.info-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.budget-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.info-item {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.budget-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.budget-card p {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: #777;
}

.info-item.full {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: #888;
}

.info-value {
  font-size: 13px;
  line-height: 1.55;
}

.toggle-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.toggle-card {
  padding: 14px;
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.toggle-card input {
  margin-top: 3px;
}

.toggle-title {
  display: block;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 4px;
}

.toggle-card p {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: #777;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #fff7f2;
  color: #b04c18;
  font-size: 12px;
}

.progress-number {
  margin-left: auto;
  font-weight: 700;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 111, 61, 0.2);
  border-top-color: #ff6f3d;
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

.inline-error,
.empty-module-state,
.event-empty {
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 12px;
}

.inline-error {
  background: #fff1f0;
  color: #c62828;
  border: 1px solid #ffd9d6;
}

.empty-module-state,
.event-empty {
  background: #fafafa;
  color: #666;
  border: 1px dashed #ddd;
}

.project-grid {
  grid-template-columns: 1fr;
}

.project-card-button {
  text-align: left;
  padding: 14px;
  cursor: pointer;
}

.project-card-name {
  font-size: 14px;
  font-weight: 700;
}

.project-card-desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.55;
  color: #666;
}

.project-card-id {
  margin-top: 10px;
  font-size: 11px;
  color: #888;
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.badge.pending {
  background: #f5f5f5;
  color: #777;
}

.badge.processing {
  background: #fff2e8;
  color: #d96c24;
}

.badge.success {
  background: #edf8ec;
  color: #2e7d32;
}

.badge.accent {
  background: #eef3ff;
  color: #2948a3;
}

.badge.danger {
  background: #fff1f0;
  color: #c62828;
}

.badge.soft {
  background: #f6f6f6;
  color: #666;
}

.config-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.platform-grid,
.event-grid {
  grid-template-columns: 1fr 1fr;
}

.platform-card,
.event-card {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.platform-head span:first-child,
.event-title {
  font-size: 13px;
  font-weight: 700;
}

.platform-metrics,
.event-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  color: #666;
}

.event-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 12px;
}

.system-logs {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.log-toggle-row {
  position: sticky;
  bottom: 0;
  z-index: 4;
  display: flex;
  justify-content: flex-end;
  padding: 10px 0 0;
  background: #fcfcfc;
}

.log-toggle-btn {
  border: 1px solid #dedede;
  background: #fff;
  color: #111;
  border-radius: 8px;
  padding: 8px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  cursor: pointer;
}

.log-toggle-btn.active {
  background: #111;
  border-color: #111;
  color: #fff;
}

.log-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.log-id,
.mono {
  font-family: 'JetBrains Mono', monospace;
}

.log-content {
  max-height: 220px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
}

.log-line {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 10px;
}

.log-time {
  color: #999;
  font-family: 'JetBrains Mono', monospace;
}

.log-msg {
  color: #444;
  line-height: 1.5;
}

.empty-state {
  min-height: 320px;
  display: grid;
  place-items: center;
  text-align: center;
  gap: 8px;
  color: #777;
}

.empty-mark {
  font-family: 'JetBrains Mono', monospace;
  font-size: 28px;
  font-weight: 700;
  color: #ccc;
}

@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1200px) {
  .content-area {
    grid-template-columns: 1fr;
  }

  .roster-shell {
    border-right: none;
    border-bottom: 1px solid #eaeaea;
    min-height: 55vh;
  }
}

@media (max-width: 768px) {
  .app-header {
    height: auto;
    padding: 14px 16px;
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }

  .header-center {
    position: static;
    transform: none;
  }

  .header-left,
  .header-right,
  .roster-toolbar,
  .runtime-feed-head,
  .explorer-ready,
  .card-header,
  .log-header {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-strip,
  .runtime-feed-stats,
  .info-grid,
  .budget-grid,
  .toggle-grid,
  .platform-grid,
  .event-grid,
  .profile-stats {
    grid-template-columns: 1fr;
  }

  .panel-header {
    height: auto;
    padding: 14px 16px;
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .panel-body,
  .scroll-container {
    padding: 14px;
  }

  .profile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
