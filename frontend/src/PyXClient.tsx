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
    functionArguments: {[key: string]: any};    // Stores the arguments for functions.
    constructor() {
        this.websocket = new WebSocket("ws://" + window.location.host + "/ws");
        this.setters = new Map();
        this.rootIdSetter = null;
        this.useRenderable = useRenderable.bind(this);
        this.useRootId = useRootId.bind(this);
        this.websocket.onmessage = this.onMessage.bind(this);
        this.resources = {};
        this.functionArguments = {};
    }

    onMessage(msg: MessageEvent) {
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
        else if (event === "function_return") {
            const call_id = data["call_id"];
            // const result = data["return"];
            delete this.functionArguments[call_id];
        } else if (event === "request") {
            const request_id = data["id"];
            const request_data = data["data"];
            
            if (request_data.event === "get_function_argument") {
                const call_id = request_data.data["call_id"];
                const path = request_data.data["path"];
                const arg = path.reduce((obj: any, key: any) => obj[key], this.functionArguments[call_id]);
                this.websocket.send(JSON.stringify({event: "response", data: {id: request_id, data: arg}}));
            }
        }
    }

    preload(jsobj: any, structure: any) {
        const result: any = {};
        for (const key in structure) {
            const parsed_key = JSON.parse(key);
            if (structure[key] === null) {
                result[key] = jsobj[parsed_key];
            } else {
                result[key] = this.preload(jsobj[parsed_key], structure[key]);
            }
        }
        return result;
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
                    const preload_args = obj["preload_args"];
                    // TODO: Add argument support.
                    return (...args: any[]) => {
                        const call_id = Math.random().toString(36).substring(7);
                        this.functionArguments[call_id] = args;
                        let preloaded_data = {};
                        console.log('preload_args', preload_args);
                        if (preload_args !== null) {
                            preloaded_data = this.preload(args, preload_args);
                        }
                        console.log('preloaded_data', preloaded_data)
                        this.websocket.send(JSON.stringify({
                            event: "resource_event",
                            data: {
                                id: id,
                                data: {
                                    event: "call",
                                    data: {
                                        call_id,
                                        arg_count: args.length,
                                        preloaded_data
                                    }
                                }
                            }
                        }));
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

