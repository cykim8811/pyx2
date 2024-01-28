
import hashlib
from typing import Dict, Set, TypeVar

from .element import PyXElement


# Define types
Hash = str

def hashResource(resource):
    return hashlib.md5(id(resource).to_bytes(8, 'big')).hexdigest()

class Resource:
    def __init__(self, data):
        self.data = data
        self.refCount = 0
        self.hash = hashResource(data)

T = TypeVar('T')
class ReferenceGraph:
    def __init__(self, root: T):
        self.nodes: Dict[T, Set[T]] = {root: set()}
        self.referenceCount: Dict[T, int] = {root: 1}   # Reference count of root is always 1
    
    def createEdge(self, fromNode: T, toNode: T):
        if toNode not in self.nodes:
            raise Exception("Cannot create edge to non-existent node")
        if toNode not in self.nodes[fromNode]:
            self.referenceCount[toNode] += 1
            self.nodes[fromNode].add(toNode)

    def deleteEdge(self, fromNode: T, toNode: T):
        if toNode in self.nodes[fromNode]:
            self.referenceCount[toNode] -= 1
            self.nodes[fromNode].remove(toNode)
        else:
            raise Exception("Cannot delete non-existent edge")
    
    def hasNode(self, node: T):
        return node in self.nodes

    def hasEdge(self, fromNode: T, toNode: T):
        if fromNode not in self.nodes:
            raise Exception("Cannot check edge from non-existent node")
        return toNode in self.nodes[fromNode]

    def getEdges(self, fromNode: T):
        if fromNode not in self.nodes:
            raise Exception("Cannot get edges from non-existent node")
        return self.nodes[fromNode]

    def createNode(self, node: T):
        if node in self.nodes:
            raise Exception("Cannot create existing node")
        self.nodes[node] = set()
        self.referenceCount[node] = 0

    def deleteNode(self, node: T):
        if node not in self.nodes:
            raise Exception("Cannot delete non-existent node")
        for ref in self.nodes[node]:
            self.deleteEdge(node, ref)
        del self.nodes[node]
        del self.referenceCount[node]
    
    def updateGraph(self, node: T, newReferences: Set[T]):
        # TODO: Check circular references
        added_nodes: Set[T] = newReferences - self.nodes[node]
        removed_nodes: Set[T] = self.nodes[node] - newReferences

        created_nodes: Set[T] = set()
        deleted_nodes: Set[T] = set()

        for toNode in added_nodes:
            if not self.hasNode(toNode):
                self.createNode(toNode)
                created_nodes.add(toNode)
            if not self.hasEdge(node, toNode):
                self.createEdge(node, toNode)
        
        for toNode in removed_nodes:
            if self.hasEdge(node, toNode):
                self.deleteEdge(node, toNode)
            if self.referenceCount[toNode] == 0:
                self.deleteNode(toNode)
                deleted_nodes.add(toNode)

        self.nodes[node] = newReferences
        
        return created_nodes, deleted_nodes


class RenderableResource(Resource):
    pass

class FunctionResource(Resource):
    pass

class ImageResource(Resource):
    pass

class TextResource(Resource):
    pass


class ResourceManager:
    def __init__(self, root: object):
        self.root = RenderableResource(root)
        self.resources = {
            hashResource(root): self.root
        }
        self.incRefCount(self.root.hash)    # Root resource has refCount of 1
        
        self._references = []   # Temporary variable for serialization

    def registerResource(self, resource: object):
        if resource.hash in self.resources:
            raise Exception("Cannot register existing resource")
        self.resources[resource.hash] = resource

    def incRefCount(self, resource_hash: Hash):
        if resource_hash not in self.resources:
            raise Exception("Cannot increment refCount of non-existent resource")
        self.resources[resource_hash].refCount += 1

    def decRefCount(self, resource_hash: Hash):
        if resource_hash not in self.resources:
            raise Exception("Cannot decrement refCount of non-existent resource")
        self.resources[resource_hash].refCount -= 1
        if self.resources[resource_hash].refCount == 0:
            del self.resources[resource_hash]

    def serializeElement(self, element: PyXElement):
        self._references = []
        serialized = self._serialize(element)
        refernces = self._references
        self._references = []
        return serialized, refernces
    
    def _serialize(self, element: object):
        if isinstance(element, PyXElement):
            return {
                '__type__': 'PyXElement',
                'tag': element.tag,
                'props': self._serialize(element.props),
                'children': self._serialize(element.children),
            }
        elif type(element) in [str, int, float, bool, type(None)]:
            return element
        elif isinstance(element, dict):
            return {key: self._serialize(value) for key, value in element.items()}
        elif isinstance(element, list):
            return [self._serialize(value) for value in element]
        elif isinstance(element, tuple):
            return tuple(self._serialize(value) for value in element)
        elif isinstance(element, set):
            return {self._serialize(value) for value in element}
        elif hasattr(element, '__render__'):
            resource_hash = hashResource(element)
            resource = None
            if resource_hash not in self.resources:
                resource = RenderableResource(element)
                self.registerResource(resource)
            else:
                resource = self.resources[resource_hash]
            self._references.append(resource)
            return {
                '__type__': 'Renderable',
                'id': hashResource(element),
            }
        elif callable(element):
            resource_hash = hashResource(element)
            resource = None
            if resource_hash not in self.resources:
                resource = FunctionResource(element)
                self.registerResource(resource)
            else:
                resource = self.resources[resource_hash]
            self._references.append(resource)
            return {
                '__type__': 'Function',
                'id': hashResource(element),
            }
        else:
            raise Exception(f"Cannot serialize unknown element type {type(element)}")

