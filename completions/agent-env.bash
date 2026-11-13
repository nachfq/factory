# Bash completion for agent-env. Environment names come from Incus, not local state.
_agent_env_complete() {
  local current=${COMP_WORDS[COMP_CWORD]} name
  COMPREPLY=()
  if (( COMP_CWORD == 1 )); then
    mapfile -t COMPREPLY < <(compgen -W 'new open open-all list remove' -- "$current")
  elif (( COMP_CWORD == 2 )) && [[ ${COMP_WORDS[1]} == open || ${COMP_WORDS[1]} == remove ]]; then
    while IFS= read -r name; do
      [[ $name == "$current"* ]] && COMPREPLY+=("$name")
    done < <(timeout 3s agent-env list --names 2>/dev/null)
  fi
  return 0
}
complete -F _agent_env_complete agent-env
