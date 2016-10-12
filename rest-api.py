# coding: utf-8

from flask import Flask, render_template, Response, send_from_directory
from flask_socketio import SocketIO, emit
import xml.etree.ElementTree as ET
import pigpio
import json


app = Flask(__name__)
app.config['SECRET_KEY'] = 'bt6/8Btb67)87(N)9nF&d$VKLJkljbaVUIuv676b/&9'
socketio = SocketIO(app)
pi = pigpio.pi()

pins = {
    23: {'name': 'Dimmer', 'state': 0, 'type': 'pwm', 'status': 'Apagado',
         'icon': 'luz', 'status-off': 'Apagado', 'status-on': 'Encendido',
         'msg-on': u'Se encendió el dimmer', 'msg-off': u'Se apagó el dimmer'},
    10: {'name': 'Fuente', 'state': 0, 'type': 'on-off', 'status': 'Apagada',
         'icon': 'none', 'status-off': 'Apagada', 'status-on': 'Encendida',
         'msg-on': u'Se encendió la fuente', 'msg-off': u'Se apagó la fuente'},
    9: {'name': 'Ventilador', 'state': 0, 'type': 'on-off', 'status': 'Apagado',
        'icon': 'luz', 'status-off': 'Apagado', 'status-on': 'Encendido',
        'msg-on': u'Se encendió el ventilador', 'msg-off': u'Se apagó el ventilador'},
    11: {'name': 'Puerta', 'state': 0, 'type': 'on-off', 'status': 'Cerrada',
         'icon': 'none', 'status-off': 'Cerrada', 'status-on': 'Abierta',
         'msg-on': u'Se abrió la puerta', 'msg-off': u'Se cerró la puerta'}
}

rgb = {
    'red': {'pin': 25, 'value': 0},
    'green': {'pin': 8, 'value': 0},
    'blue': {'pin': 7, 'value': 0}
}

rgb_auto = False

for pin in pins:
    pi.set_mode(pin, pigpio.OUTPUT)
    if pins[pin]['type'] == 'pwm':
        pi.set_PWM_frequency(pin, 600)
        pi.set_PWM_range(pin, 100)
    pi.write(pin, 0)


for color in rgb:
    pin = rgb[color]['pin']
    pi.set_mode(pin, pigpio.OUTPUT)
    pi.set_PWM_frequency(pin, 600)
    pi.set_PWM_range(pin, 255)
    pi.write(pin, 0)


@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)


@app.route('/img/<path:path>')
def send_img(path):
    return send_from_directory('img', path)


@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)


@app.route("/")
def main():
    for pin in pins:
        pins[pin]['state'] = pi.read(pin)
    template_data = {
        'pins': pins
    }

    return render_template('main.html', **template_data)


@app.route("/rest/<change_pin>/<action>", defaults={'duty': None})
@app.route("/rest/<change_pin>/<action>/<duty>")
def action(change_pin, action, duty):
    change_pin = int(change_pin)
    if duty is not None:
        duty = int(duty)
    device_name = pins[change_pin]['name']

    if action == "on":
        pi.write(change_pin, 1)
        pins[change_pin]['state'] = 100
        message = u"" + pins[change_pin]['msg-on']
        icono = pins[change_pin]['icon'] + '-on'
        pins[change_pin]['status'] = pins[change_pin]['status-on']
    if action == "off":
        pi.write(change_pin, 0)
        pins[change_pin]['state'] = 0
        message = u"" + pins[change_pin]['msg-off']
        icono = pins[change_pin]['icon'] + '-off'
        pins[change_pin]['status'] = pins[change_pin]['status-off']
    if action == "pwm":
        pi.set_PWM_dutycycle(change_pin, duty)
        pins[change_pin]['state'] = duty
        message = u"" + device_name + " encendida en: " + str(duty) + "%"
        icono = 'luz-on'
        pins[change_pin]['status'] = 'Encendido al ' + str(duty) + "%"

    for pin in pins:
        if pins[pin]['type'] == 'on-off':
            pins[pin]['state'] = pi.read(pin) * 100

    template_data = {
        'pins': pins,
        'message': message,
    }
    socketio.emit('message', {'message': message, 'icon':
                  icono, 'target': str(change_pin),
                  'status': pins[change_pin]['status']})

    return render_template('main.html', **template_data)


@app.route("/rest/rgb/<red>/<green>/<blue>")
def rest_rgb(red, green, blue):
    global rgb_auto
    new_values = {'red': int(red), 'green': int(green), 'blue': int(blue)}

    for color in rgb:
        duty = new_values[color]
        pi.set_PWM_dutycycle(rgb[color]['pin'], duty)
        rgb[color]['value'] = duty

    socketio.emit('rgb', {'message': "Changed RGB color", 'json': json.dumps(rgb)})

    rgb_auto = False
    socketio.emit('rgb_auto', {'auto': rgb_auto})

    return Response(json.dumps(rgb), mimetype='text/json')


@app.route("/rest/rgb/<auto>")
def rgb_auto_fn(auto):
    global rgb_auto
    rgb_auto = auto == "True"
    socketio.emit('rgb_auto', {'auto': rgb_auto})
    return Response({'auto': str(rgb_auto)}, mimetype='text/json')


@app.route("/rest/status")
def status():
    rainbow = str(int(rgb_auto))
    nodes = ET.Element("nodes")
    for pin in pins:
        node = ET.SubElement(nodes, "node", id=str(pin))
        prop = ET.SubElement(node, "property", value=str(pins[pin]['state']))

    node = ET.SubElement(nodes, "node", id='auto_rgb')
    prop = ET.SubElement(node, "property", value=rainbow)
    return Response(ET.tostring(nodes), mimetype='text/xml')


@app.route("/gui")
def gui():
    template_data = {'pins': pins}
    return render_template('gui.html', **template_data)


@app.route("/colorpicker")
def picker():
    template_data = {}
    return render_template('picker.html', **template_data)


@socketio.on('my event')
def my_event_handler(json):
    print('received json: ' + str(json))
    emit('my response', json)


@socketio.on('rgb_change')
def rgb_change(colors):
    for color in rgb:
        duty = colors[color]
        pi.set_PWM_dutycycle(rgb[color]['pin'], duty)
        rgb[color]['value'] = duty
    print colors

if __name__ == "__main__":
    #app.run(host='0.0.0.0', port=8001, debug=True)
    socketio.run(app, host='0.0.0.0', port=8001, debug=True)
