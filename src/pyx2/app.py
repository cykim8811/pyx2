
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, FileResponse, Response
from starlette.endpoints import WebSocketEndpoint
from starlette.websockets import WebSocket

import asyncio
import os
import io
import random

from typing import Dict, Set

from .resource import RenderableResource, ReferenceGraph, ResourceManager, Hash, hashResource, Resource

from .context import current

class RequestManager:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.requests: Dict[int, asyncio.Future] = {}
    
    def request(self, data):
        request_id = random.randint(0, 2**32).to_bytes(4, 'big').hex()
        loop = asyncio.get_event_loop()
        loop.create_task(self.websocket.send_json({'event': 'request', 'data': {'id': request_id, 'data': data}}))
        future = asyncio.Future()
        self.requests[request_id] = future
        return future
    
    def response(self, data):
        request_id = data['id']
        if request_id in self.requests:
            self.requests[request_id].set_result(data['data'])
            del self.requests[request_id]
        else:
            raise Exception("Cannot respond to non-existent request")

class Client:
    def __init__(self, websocket: WebSocket, root: RenderableResource, resourceManager: ResourceManager):
        self.websocket: WebSocket = websocket
        self.root: RenderableResource = root
        self.referenceGraph: ReferenceGraph[Hash] = ReferenceGraph(root.hash)
        self.resourceManager: ResourceManager = resourceManager
        self.requestManager: RequestManager = RequestManager(websocket)
        self.data: Dict[str, object] = {}
    
    def request(self, data):
        return self.requestManager.request(data)

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

        current.user = self.client
        self.application.onConnect()

        # Send root resource hash
        await websocket.send_json({'event': 'root', 'data': self.client.root.hash})

        # Send initial render
        self.client.rerender(self.application.component)

    async def on_receive(self, websocket, data):
        try:
            if data['event'] == 'resource_event':
                resource_hash: Hash = data['data']['id']
                if resource_hash not in self.client.referenceGraph.nodes:
                    # Resource should be in referenceGraph to be accessible (for security reasons)
                    raise Exception("Cannot call non-existent resource")
                
                resource: Resource = self.application.resource_manager.resources[resource_hash]
                resource.event(data['data']['data'], self.client)
            elif data['event'] == 'response':
                self.client.requestManager.response(data['data'])
            else:
                raise Exception("Invalid event")
        except Exception as e:
            import traceback
            traceback.print_exc()


    async def on_disconnect(self, websocket, close_code):
        current.user = self.client
        self.application.onDisconnect()
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
        
        @self.route('/images/{filename}')
        async def images(request):
            # filename: RESOURCE_HASH.png
            filename = request.path_params['filename']
            resource_hash = filename.split('.')[0]
            if resource_hash in self.resource_manager.resources:
                pil_img = self.resource_manager.resources[resource_hash].data
                # Do not save the image to disk, serve it directly.
                # Change PIL.Image to png bytes
                img_bytes = io.BytesIO()
                pil_img.save(img_bytes, format='PNG')
                img_bytes = img_bytes.getvalue()
                return Response(content=img_bytes, media_type="image/png")
            else:
                return HTMLResponse("Image not found", status_code=404)

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

    def onConnect(self):
        pass

    def onDisconnect(self):
        pass

