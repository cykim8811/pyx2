import { useMemo } from "react";
import { PyXClient } from "./PyXClient";


function App() {
  const client = useMemo(() => new PyXClient(), []);
  console.log(111);
  const rootId = client.useRootId();
  console.log('rootId', rootId);
  const rootElement = client.useRenderable(rootId);
  console.log('rootElement', rootElement);
  return rootElement;
}

export default App;
