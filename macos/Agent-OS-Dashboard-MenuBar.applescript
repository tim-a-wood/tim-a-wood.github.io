-- Placeholder __MV_REPO_PATH__ is replaced by macos/install_agent_os_launcher_app.sh
on run
	set mvRepo to "__MV_REPO_PATH__"
	do shell script "cd " & quoted form of mvRepo & " && bash scripts/start_agent_os_dashboard.sh"
end run
