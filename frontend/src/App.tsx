import { useMemo } from "react";
import { PyXClient } from "./PyXClient";


function App() {
  const client = useMemo(() => new PyXClient(), []);
  const rootId = client.useRootId();
  const rootElement = client.useRenderable(rootId);
  return rootElement;
}

export default App;
