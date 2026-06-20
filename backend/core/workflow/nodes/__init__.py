"""LangGraph node functions package.

Each node is a thin orchestration layer that:
1. Records execution start via begin_node_execution()
2. Delegates to a domain service
3. Returns a partial state dict with the field it writes
4. Handles exceptions by appending WorkflowError and re-raising fatal ones
"""
