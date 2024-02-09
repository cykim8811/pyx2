

class PyXElement:
    def __init__(self, tag, props, *children):
        self.tag = tag
        self.props = props
        self.children = children

def createElement(tag, props, *children):
    return PyXElement(tag, props, *children)

