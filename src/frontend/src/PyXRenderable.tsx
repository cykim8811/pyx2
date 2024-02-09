import { PyXClient } from "./PyXClient"


export default function PyXRenderable({client, id}: {client: PyXClient, id: string}) {
    const element = client.useRenderable(id);
    return element;
}