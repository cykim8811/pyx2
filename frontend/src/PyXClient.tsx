/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { Dispatch, SetStateAction, useEffect, useState } from "react";
import PyXRenderable from "./PyXRenderable";

function useRootId(this: PyXClient): string | null {
    const [rootId, setRootId] = useState<string | null>(null);
    if (this.rootIdSetter === null) {
        this.rootIdSetter = setRootId;
    }
    return rootId;
}

function useRenderable(this: PyXClient, resourceId: string | null): React.ReactNode {
    const [element, setElement] = useState<React.ReactNode>(null);
    useEffect(() => {
        if (resourceId !== null) {
            this.setters.set(resourceId, setElement);
            if (resourceId in this.resources) {
                setElement(this.convert(this.resources[resourceId]));
            }
        }
    }, [resourceId]);
    return element;
}


export class PyXClient {
    private websocket: WebSocket;
    setters: Map<string, Dispatch<SetStateAction<React.ReactNode>>>;
    rootIdSetter: Dispatch<SetStateAction<string | null>> | null;
    useRenderable: (resourceId: string|null) => React.ReactNode;
    useRootId: () => string | null;
    resources: {[key: string]: object};
    constructor() {
        this.websocket = new WebSocket("ws://" + window.location.host + "/ws");
        this.setters = new Map();
        this.rootIdSetter = null;
        this.useRenderable = useRenderable.bind(this);
        this.useRootId = useRootId.bind(this);
        this.websocket.onmessage = this.onMessage.bind(this);
        this.resources = {};
    }

    onMessage(msg: MessageEvent) {
        console.log(msg);
        const {event, data} = JSON.parse(msg.data);
        if (event === "root") {
            this.rootIdSetter!(data);
        }
        else if (event === "render") {
            for (const key in data) {
                this.resources[key] = data[key];
            }
            for (const [key, setter] of this.setters) {
                if (key in data) {
                    setter(this.convert(data[key]));
                }
            }
        }
    }

    convert(obj: any): any {
        // If obj is one of the primitive types, return it.
        if (typeof obj !== "object" || obj === null) {
            return obj;
        } else if (obj instanceof Array) {
            return obj.map(this.convert.bind(this));
        } else if (obj instanceof Object) {
            if (Object.prototype.hasOwnProperty.call(obj, "__type__")) {
                const resourceType = obj["__type__"];
                if (resourceType === "Renderable") {
                    const id = obj["id"];
                    return <PyXRenderable client={this} id={id} />;
                } else if (resourceType === "PyXElement") {
                    const tag = obj["tag"];
                    const props = this.convert(obj["props"]);
                    const children = this.convert(obj["children"]);
                    return React.createElement(tag, props, children);
                } else if (resourceType === "Function") {
                    const id = obj["id"];
                    // TODO: Add argument support.
                    return () => {
                        console.log("Calling function", id);
                        this.websocket.send(JSON.stringify({event: "call", data: {id}}));
                    };
                }
            } else {
                const newObj: any = {};
                for (const key in obj) {
                    newObj[key] = this.convert(obj[key]);
                }
                return newObj;
            }
        }
    }
}

