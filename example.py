

from pyx2 import PyX, createElement, current


class Display:
    def __init__(self, text):
        self.text = text

    def __render__(self):
        return createElement('div', {}, self.text)


class MyComponent:
    def __init__(self):
        self.count = 3
        self.display = Display('Hello World')

    async def onClick(self, e):
        for i in range(5):
            print(await e.button)
        self.count += 1
        self.display.text = 'Hello World ' + str(self.count)
        current.app.rerender(self)

    def __render__(self):
        elems = []
        
        for i in range(self.count):
            elems.append(createElement('li', {}, f'Item {i}'))
        
        async def onUsernameInput(e):
            self.
        
        return createElement('div', {}, [
            self.display,
            str(current.user),
            createElement('h1', {}, 'Count:', self.count),
            createElement('button', {'onClick': self.onClick}, 'Click me!'),
            createElement('div', {}, 
                createElement('input', {'type': 'text',
                createElement('input', {'type': 'password'}),
            ),
        ])

component = MyComponent()

app = PyX(component)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=7004)

