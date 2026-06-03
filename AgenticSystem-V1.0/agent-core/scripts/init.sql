CREATE TABLE IF NOT EXISTS agent_states (
    agent_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    skill_set JSON NOT NULL,
    memory LONGTEXT,
    task_stack JSON,
    workflow_context JSON,
    current_step INT DEFAULT 0,
    scratch_pad JSON,
    status ENUM('running', 'paused', 'terminated') DEFAULT 'running',
    version INT DEFAULT 1,
    created_at DATETIME NOT NULL,
    last_checkpoint DATETIME NOT NULL,
    INDEX idx_session (session_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_state_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    event_type ENUM('pause', 'resume', 'destroy', 'migrate', 'checkpoint') NOT NULL,
    state_snapshot JSON,
    created_at DATETIME NOT NULL,
    INDEX idx_agent_event (agent_id, event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    workflow_name VARCHAR(128) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    step_index INT NOT NULL,
    step_name VARCHAR(128) NOT NULL,
    context_data LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (workflow_name, agent_id, step_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
