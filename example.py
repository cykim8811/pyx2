

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

    def onClick(self):
        self.count += 1
        self.display.text = 'Hello World ' + str(self.count)
        print('Clicked', self.count)
        current.app.rerender(self)

    def __render__(self):
        elems = []
        for i in range(self.count):
            elems.append(createElement('li', {}, f'Item {i}'))
    
        # print(self.onClick.__qualname__)
        
        return createElement('div', {}, [
            self.display,
            str(current.user),
            createElement('h1', {}, 'Count:', self.count),
            createElement('button', {'onClick': self.onClick}, 'Click me!'),
            createElement('ul', {}, elems),
        ])

component = MyComponent()

app = PyX(component)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=7004)

