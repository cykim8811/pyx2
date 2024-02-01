
import hashlib
import inspect
import asyncio
import json
from typing import Dict, Set, TypeVar

from .element import PyXElement
from .utils import static_vars


# Define types
Hash = str

def hashResource(resource):
    return hashlib.md5(id(resource).to_bytes(8, 'big')).hexdigest()

class Resource:
    def __init__(self, data):
        self.data = data
        self.refCount = 0
        self.hash = hashResource(data)
    
    def event(self, data, client):
        pass

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
            self.referenceCount[ref] -= 1
            if self.referenceCount[ref]== 0:
                self.deleteNode(ref)
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


class FunctionPreloader:
    def __init__(self):
        self.preload_map = {}
    
    def use_attr(self, preload_key: str, path: list):
        if preload_key not in self.preload_map:
            self.preload_map[preload_key] = dict()
        current = self.preload_map[preload_key]
        for key in path[:-1]:
            key = json.dumps(key)
            if key not in current:
                current[key] = {}
            current = current[key]
        current[json.dumps(path[-1])] = None
    
    def get(self, preload_key: str):
        return self.preload_map[preload_key] if preload_key in self.preload_map else {}


class FunctionArgument:
    def __init__(self, path: list, call_id: str, client, data, preloader: FunctionPreloader, preload_key: str, parent=None):
        self._path = path
        self._call_id = call_id
        self._client = client
        self._preloader = preloader
        self._preload_key = preload_key
        self._data = data
        self._parent = parent
    
    def __getitem__(self, key):
        stringified_key = json.dumps(key)
        return FunctionArgument(self._path + [key], self._client, self._data[stringified_key] if (self._data is not None and stringified_key in self._data) else None, self._preloader, self._preload_key, self)
    
    def __getattribute__(self, name):
        if name in ['_path', '_call_id', '_client', '_preloader', '_preload_key', '_data', '_parent', 'set_data']:
            return super().__getattribute__(name)
        stringified_key = json.dumps(name)
        return FunctionArgument(self._path + [name], self._call_id, self._client, self._data[stringified_key] if (self._data is not None and stringified_key in self._data) else None, self._preloader, self._preload_key, self)

    def set_data(self, key, data):
        stringified_key = json.dumps(key)
        if self._data is None:
            self._data = {}
        self._data[stringified_key] = data
        if self._parent is not None:
            self._parent.set_data(self._path[-1], self._data)

    def __await__(self):
        async def ftn():
            self._preloader.use_attr(self._preload_key, self._path)
            if self._data is not None:
                return self._data
            res = await self._client.request({'event': 'get_function_argument', 'data': {'path': self._path, 'call_id': self._call_id}})
            self._data = res
            self._parent.set_data(self._path[-1], res)
            return res
        return ftn().__await__()


class FunctionResource(Resource):
    preloader = FunctionPreloader()
    def event(self, data, client):
        if data['event'] == 'call':
            arg_count: list = data['data']['arg_count']
            call_id: str = data['data']['call_id']
            preloaded_data: dict = data['data']['preloaded_data'] if 'preloaded_data' in data['data'] else {}

            # Check if number of arguments is valid
            # TODO: Add support for keyword arguments or variable arguments
            arg_min = None
            arg_max = None
            if not callable(self.data):
                raise Exception("Cannot call non-callable resource")
            if inspect.ismethod(self.data):
                arg_max = self.data.__code__.co_argcount - 1 # Subtract 1 for self
                arg_min = arg_max - len(self.data.__defaults__) if self.data.__defaults__ is not None else arg_max
            elif inspect.isfunction(self.data):
                arg_max = self.data.__code__.co_argcount
                arg_min = arg_max - len(self.data.__defaults__) if self.data.__defaults__ is not None else arg_max
            else:   # An object with __call__ method
                arg_max = self.data.__call__.__code__.co_argcount - 1 # Subtract 1 for self
                arg_min = arg_max - len(self.data.__call__.__defaults__) if self.data.__call__.__defaults__ is not None else arg_max

            assert arg_count >= arg_min, f"Number of arguments must be at least {arg_min}"

            # Create arguments
            args = [
                FunctionArgument([i], call_id, client, preloaded_data[json.dumps(i)] if json.dumps(i) in preloaded_data else {}, self.preloader, self.data.__qualname__)
                for i in range(min(arg_count, arg_max))
            ]

            # Call function - TODO: Just call the function and if it returns a coroutine, create a task
            if inspect.iscoroutinefunction(self.data):
                async def ftn_call():
                    result = await self.data(*args)
                    await client.websocket.send_json({'event': 'function_return', 'data': {'call_id': call_id, 'return': result}})
                asyncio.create_task(ftn_call())
            else:
                result = self.data(*args)
                loop = asyncio.get_event_loop()
                loop.create_task(client.websocket.send_json({'event': 'function_return', 'data': {'call_id': call_id, 'return': result}}))

    def get_preload_args(self):
        return self.preloader.get(self.data.__qualname__)

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
                'preload_args': self.resources[resource_hash].get_preload_args(),
            }
        else:
            raise Exception(f"Cannot serialize unknown element type {type(element)}")

