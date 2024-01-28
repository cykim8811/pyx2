
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, FileResponse
from starlette.endpoints import WebSocketEndpoint
from starlette.websockets import WebSocket
from starlette.background import BackgroundTasks

import uvicorn
import asyncio
import os

from typing import TypeVar, Dict, Set

from .resource import RenderableResource, ReferenceGraph, ResourceManager, Hash, hashResource
from .element import PyXElement

from .context import current

class Client:
    def __init__(self, websocket: WebSocket, root: RenderableResource, resourceManager: ResourceManager):
        self.websocket: WebSocket = websocket
        self.root: RenderableResource = root
        self.referenceGraph: ReferenceGraph[Hash] = ReferenceGraph(root.hash)
        self.resourceManager: ResourceManager = resourceManager
    
    def rerender(self, element: object):
        current.user = self
        current.request = None
        result = self._rerender(element)
        asyncio.create_task(self.send_render(result))
    
    async def send_render(self, result: Dict[Hash, Dict]):
        await self.websocket.send_json({'event': 'render', 'data': result})
    
    def _rerender(self, element: object):
        resource_hash: Hash = hashResource(element)

        if not self.referenceGraph.hasNode(resource_hash):
            raise Exception("Cannot rerender non-existent resource")
        
        target_resource: RenderableResource = self.resourceManager.resources[resource_hash]

        # TODO: Set context
        # TODO: Get Dependencies
        result = target_resource.data.__render__()

        # TODO: Update dependencies

        # return serialized result and references of resources
        serialized, reference_resource_list = self.resourceManager.serializeElement(result) # Serializable Dict, List[Resource]

        # SERIALIZE function adds Resources with 0 refCount to resourceManager
        # incRefCount function must be called for resources with 0 refCount

        hashes: Set[Hash] = set()
        for reference_resource in reference_resource_list:
            hashes.add(reference_resource.hash)

        created_nodes_hash, deleted_nodes_hash = self.referenceGraph.updateGraph(resource_hash, hashes)

        for created_node_hash in created_nodes_hash:
            self.resourceManager.incRefCount(created_node_hash)

        for deleted_node_hash in deleted_nodes_hash:
            self.resourceManager.decRefCount(deleted_node_hash)
        
        assert all(self.resourceManager.resources[resource_hash].refCount > 0 for resource_hash in self.resourceManager.resources), "All resources in resourceManager must have refCount > 0"

        total_result = { resource_hash: serialized }
        
        for created_node_hash in created_nodes_hash:
            if isinstance(self.resourceManager.resources[created_node_hash], RenderableResource):
                rerender_result = self._rerender(self.resourceManager.resources[created_node_hash].data)
                total_result.update(rerender_result)
        
        return total_result
        

class PyXWebSocketEndpoint(WebSocketEndpoint):
    encoding = 'json'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.application: PyX = self.scope['app']
        self.client: Client = None
    
    async def on_connect(self, websocket):
        await websocket.accept()
        self.client = Client(websocket, self.application.resource_manager.root, self.application.resource_manager)
        self.application.clients.add(self.client)

        # Send root resource hash
        await websocket.send_json({'event': 'root', 'data': self.client.root.hash})

        # Send initial render
        self.client.rerender(self.application.component)

    async def on_receive(self, websocket, data):
        if data['event'] == 'call':
            resource_hash: Hash = data['data']['id']

            if resource_hash not in self.application.resource_manager.resources:
                raise Exception("Cannot call non-existent resource")

            resource = self.application.resource_manager.resources[resource_hash].data
            resource()
            
    async def on_disconnect(self, websocket, close_code):
        print("Closing websocket")
        self.application.clients.remove(self.client)


class PyX(Starlette):
    def __init__(self, component):
        super().__init__()
        self.component = component
        self.resource_manager = ResourceManager(component)
        self.clients = set()

        @self.route('/')
        async def homepage(request):
            # If ./public/index.html exists, serve it
            # Otherwise, serve the default index.html
            if os.path.exists('./public/index.html'):
                return HTMLResponse(open('./public/index.html').read())
            else:
                module_dir = os.path.dirname(os.path.realpath(__file__))
                return HTMLResponse(open(f'{module_dir}/assets/index.html').read())
        
        @self.route('/pyx2.js')
        async def pyx2js(request):
            module_dir = os.path.dirname(os.path.realpath(__file__))
            return FileResponse(f'{module_dir}/assets/pyx2.js')

        self.add_websocket_route('/ws', PyXWebSocketEndpoint)

    async def __call__(self, scope, receive, send):
        current.app = self
        self.initialize_public_directory()
        await super().__call__(scope, receive, send)

    def initialize_public_directory(self):
        pass

    def rerender(self, element: object):
        for client in self.clients:
            if client.referenceGraph.hasNode(hashResource(element)):
                client.rerender(element)

