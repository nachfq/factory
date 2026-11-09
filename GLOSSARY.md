# Interactive agents

Terminology for delegation between Factory's independent interactive agents. Current scope: the Pi ↔ Pi prototype described in [the plan](docs/pi-agents-prototype.md).

## Language

**Coordinator**:
The agent in the conversation from which the user delegates work and receives reports. Its authority is bounded by the user's instructions and authorizations.

**Worker**:
An independent interactive agent that receives a scoped assignment from the coordinator and with which the user can also speak directly.
_Avoid_: Hidden subagent, ephemeral process

**Assignment**:
A task that defines a worker's expected outcome, scope, and limits of action.

**Agent event**:
Communication from one agent to another, such as registration, a question, or an outcome report. It is not a human instruction or approval.
_Avoid_: User message

**Message acceptance**:
Confirmation that the recipient admitted a message for delivery to its agent. It does not confirm that the agent has read it, replied, or completed the assignment.
_Avoid_: Read receipt, task completion

**Human approval**:
Explicit authorization from the user for an action within a defined scope. A report or decision from another agent cannot replace it.
