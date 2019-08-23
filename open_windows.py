import onewire, ds18x20, time, ssd1306
from machine import I2C, Pin
import urequests
import ujson as json
import network
import uos
import ntptime
"""
Micropython ESP8266 and DS18B20 "Open the Windows" DIY Sensor
By Nathan Wells
MIT License
"""
#Display
iic = I2C(scl = Pin(2), sda = Pin(0))
oled = ssd1306.SSD1306_I2C(128, 64, iic)

#API key from https://openweathermap.org
weather_api_key = 'XXXXXXXX'
#City ID from https://openweathermap.org
city_id = "5601538" 
#Units you desire to return from https://openweathermap.org ("imperial" or "metric")
weather_units = "imperial"
#IFTT.com urls needed to push notifications to Pushbullet
ifttt_close_window_url = 'https://maker.ifttt.com/trigger/window_close/with/key/XXXXXXXXXX'
ifttt_open_window_url = 'https://maker.ifttt.com/trigger/window_open/with/key/XXXXXXXX'
#Keep a list of various WiFi networks you would like to be able to connect to
#ex. "SSID": "PASSWORD",
dict_of_wifi = {
    "SSID1": "PASSWORD1",
    "SSID2": "PASSWORD2",
    "SSID3": "PASSWORD3"
}
#If your temperature sensor is off, set an offset here
temp_offset = 6
#Your time-zone (mine is in PST which is UTC-7) for example, Singapore would be: +(8*3600)
time_zone = -(7*3600)
#The pin that you are using for the DS18B20 sensor
temperature_pin = 0


#Animated Sun Icon (so we can tell our script is running)
SUN1 = [
[ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
[ 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0],
[ 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
[ 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0],
[ 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
[ 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1],
[ 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
[ 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0],
[ 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
[ 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0],
[ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
]
SUN2 = [
[ 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
[ 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0],
[ 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
[ 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
[ 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
[ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
[ 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
[ 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
[ 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
[ 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0],
[ 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
]
#Offsets to put the sun icon in the bottom center of our 128x64 ssd1306
xoffset = 59
yoffset = 50

#Function to connect to WiFi - with 10 retries
def do_connect():
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)
    i = 1
    if not wlan.isconnected():
        for _ in range(10):
            #clear the led
            oled.fill(0)
            oled.show()
            oled.text('connecting...', 5, 5)
            oled.text('try number: ' + str(i), 5, 20)
            oled.show()
            print('connecting to network...' + str(i))
            #if not a new connection, just use cache
            wlan.connect()
            time.sleep(30)
            #If we are having trouble connecting - check available WiFi and try to connect
            #to WiFi user specificed in dict_of_wifi if available
            if not wlan.isconnected() and i == 5:
                ssid = wlan.scan()
                for x in ssid:
                    for wifi_ssid in dict_of_wifi:
                        if wifi_ssid in str(x):
                            wlan.connect(wifi_ssid, dict_of_wifi[wifi_ssid])
                            oled.text('Trying ' + str(wifi_ssid), 5, 35)
                            oled.show()
                            time.sleep(30)
                            break
                        else:
                            pass
            i += 1
            if wlan.isconnected():
                print('Connected.')
                oled.fill(0)
                oled.show()
                oled.text('connected!', 5, 25)
                oled.show()
                break
            time.sleep(30)
        else:
            print('Fail')
            oled.fill(0)
            oled.show()
            oled.text('failed', 5, 25)
            oled.show()
    print('network config:', wlan.ifconfig())
#Name of our storage text file so we keep the state of the open or closed windows on disk
path = 'push.txt'

#Function to check if a file exists
def file_exists(path):
    try:
        f = open(path, "r")
        exists = True
        f.close()
    except OSError:
        exists = False
    return exists

#Connect Temp Sensor
try:
    ds_pin = machine.Pin(temperature_pin)
    ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
    roms = ds_sensor.scan()
    print('Found DS devices: ', roms)
except Exception as e:
    print("No temperature sensor found")
    print(e)
    oled.fill(0)
    oled.show()
    oled.text('No temp', 5, 5)
    oled.text('sensor found', 5, 25)
    oled.show()
open_windows = False
close_windows = True
try:
   while True:
        #Create our state file if it doesn't exist
        #If it does exist, populate window variables based on states in file
        if file_exists(path):
            with open(path, 'r') as file:
                for line in file:
                    current_data = json.loads(line)
                    open_windows = current_data["open_window"]
                    close_windows = current_data["close_window"]
        elif not file_exists(path):
            with open(path, 'w') as file:
                current_data = { "open_window": False, "close_window": True }
                file.write(json.dumps(current_data))
        #Connect to WiFi
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            print(wlan.isconnected())
            print("not connected...")
            do_connect()
        #Wait after connecting to WiFi
        time.sleep(5)
        #Update the current time (PST)
        for x in range(10):
            if ntptime.settime():
                break
            else:
                time.sleep(1)
        current_time = time.localtime(time.mktime(time.localtime()) + time_zone)
        hour = current_time[3]
        #Get current weather
        current_temperature = 'blank'
        weather_description = 'blank'
        base_url = "http://api.openweathermap.org/data/2.5/weather?"
        complete_url = base_url + "appid=" + weather_api_key + "&id=" + city_id + "&units=" + weather_units 
        response = urequests.get(complete_url) 
        x = response.json() 
        if x["cod"] != "404": 
            y = x["main"] 
            current_temperature = y["temp"] 
            #current_pressure = y["pressure"] 
            #current_humidiy = y["humidity"] 
            z = x["weather"] 
            weather_description = z[0]["description"] 
        else: 
            print(" City Not Found ") 
        #Sometimes the sensor isn't ready, so try twice
        try:
            time.sleep(5)
            ds_sensor.convert_temp()
            pass
        except:
            time.sleep(5)
            ds_sensor.convert_temp()
        #Give time to convert the temperature before continuing
        time.sleep_ms(750)
        #Go through each of the connected temperature sensors (we just have one)
        for rom in roms:
            #Convert to imperial units if desired
            if weather_units == 'imperial':
                inside_temp = ((int(ds_sensor.read_temp(rom)) * 1.8) + 32) + temp_offset
            else:
                inside_temp = int(ds_sensor.read_temp(rom)) + temp_offset
        #clear the led
        oled.fill(0)
        oled.show()
        #Round the inside_temp to two decimal places
        inside_temp = round(inside_temp, 2)
        oled.text(str(inside_temp) + 'F Inside', 5, 5)
        oled.text(str(current_temperature) + 'F Outside', 5, 20)
        oled.text(str(weather_description), 5, 35)
        oled.show()
        #Check if we should close the windows
        if (int(current_temperature) + 2) > inside_temp and int(current_temperature) < (inside_temp + 5) and int(hour) < 15 and int(hour) > 7 and close_windows == False:
            send_message = urequests.get(ifttt_close_window_url)
            send_message.close()
            with open(path, 'w') as file:
                current_data = { "open_window": False, "close_window": True }
                file.write(json.dumps(current_data))
            close_windows = True
            open_windows = False
        #check if we should open the windows
        if int(current_temperature + 2) < inside_temp and int(current_temperature) > 45 and int(hour) > 15 and open_windows == False:
            send_message = urequests.get(ifttt_open_window_url)
            send_message.close()
            with open(path, 'w') as file:
                current_data = { "open_window": True, "close_window": False }
                file.write(json.dumps(current_data))
            open_windows = True
            close_windows = False
        for x in range(50):
            for y, row in enumerate(SUN1):
                for x, c in enumerate(row):
                    oled.pixel(x + xoffset, y + yoffset, c)
            oled.show()
            time.sleep(9)
            for y, row in enumerate(SUN2):
                for x, c in enumerate(row):
                    oled.pixel(x + xoffset, y + yoffset, c)
            oled.show()
            time.sleep(9)
except Exception as e:
    text = str(e)
    print("There was a problem")
    print(text)
    oled.fill(0)
    oled.show()
    oled.text(str(e), 5, 5)
    oled.text('Error', 5, 25)
    oled.show()
    time.sleep(30)
    machine.reset()
