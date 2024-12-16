from typing import Dict, Any, List, Optional, TypedDict
from selenium import webdriver

class AccessibilityNode(TypedDict):
    nodeId: str
    role: Dict[str, Any]
    name: Dict[str, Any]
    properties: List[Dict[str, Any]]
    bound: Optional[List[float]]
    childIds: List[str]

def get_accessibility_tree(driver: webdriver.Chrome) -> List[AccessibilityNode]:
    """Get the accessibility tree for the current page."""
    # Get full accessibility tree using Chrome DevTools Protocol
    accessibility_tree = driver.execute_cdp_cmd(
        "Accessibility.getFullAXTree", {}
    )["nodes"]
    
    # Remove duplicate nodes
    seen_ids = set()
    filtered_tree = []
    for node in accessibility_tree:
        if node["nodeId"] not in seen_ids:
            filtered_tree.append(node)
            seen_ids.add(node["nodeId"])
            
    # Get bounding rectangles for each node
    for node in filtered_tree:
        if "backendDOMNodeId" not in node:
            node["bound"] = None
            continue
            
        backend_node_id = str(node["backendDOMNodeId"])
        if node["role"]["value"] == "RootWebArea":
            node["bound"] = [0.0, 0.0, 10.0, 10.0]
        else:
            try:
                # Get element position and size
                response = driver.execute_cdp_cmd(
                    "DOM.getBoxModel",
                    {"backendNodeId": int(backend_node_id)}
                )
                if "model" in response:
                    quad = response["model"]["border"]
                    x = quad[0]
                    y = quad[1]
                    width = quad[2] - x
                    height = quad[5] - y
                    node["bound"] = [x, y, width, height]
                else:
                    node["bound"] = None
            except:
                node["bound"] = None
                
    return filtered_tree

def format_accessibility_tree(tree: List[AccessibilityNode]) -> str:
    """Format accessibility tree as a string for the LLM."""
    def node_to_str(node: AccessibilityNode) -> str:
        role = node["role"]["value"]
        name = node["name"].get("value", "")
        bound = node["bound"]
        
        # Format properties
        props = []
        for prop in node.get("properties", []):
            if prop["name"] in ["focused", "required", "disabled"]:
                props.append(f"{prop['name']}={prop['value']['value']}")
                
        # Build node description
        desc = [f"{role}"]
        if name:
            desc.append(f'"{name}"')
        if props:
            desc.append(f"[{', '.join(props)}]")
        if bound:
            desc.append(f"@({bound[0]:.0f},{bound[1]:.0f},{bound[2]:.0f},{bound[3]:.0f})")
            
        return " ".join(desc)
    
    # Build tree representation
    def build_tree(node_id: str, nodes_map: Dict[str, AccessibilityNode], depth: int = 0) -> str:
        if node_id not in nodes_map:
            return ""
            
        node = nodes_map[node_id]
        node_str = "  " * depth + node_to_str(node) + "\n"
        
        for child_id in node.get("childIds", []):
            node_str += build_tree(child_id, nodes_map, depth + 1)
            
        return node_str
        
    # Create node map for easy lookup
    nodes_map = {node["nodeId"]: node for node in tree}
    
    # Find root node
    root_node = next(
        (node for node in tree if node["role"]["value"] == "RootWebArea"),
        tree[0]  # Fallback to first node if no root found
    )
    
    return build_tree(root_node["nodeId"], nodes_map)
