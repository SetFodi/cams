        document.getElementById('setTimeBtn').addEventListener('click', function() {
            const dayTime = document.getElementById('day_time').value;
            const nightTime = document.getElementById('night_time').value;

            fetch('/set_time_profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `day_time=${dayTime}&night_time=${nightTime}`
            }).then(response => response.json())
              .then(data => {
                  alert("Profile times set: " + JSON.stringify(data));
              });
        });

        document.getElementById('dayBtn').addEventListener('click', function() {
            fetch('/set_day_mode', { method: 'POST' }).then(response => response.json())
                .then(data => alert(data.message));
        });

        document.getElementById('nightBtn').addEventListener('click', function() {
            fetch('/set_night_mode', { method: 'POST' }).then(response => response.json())
                .then(data => alert(data.message));
        });

        document.getElementById('refreshBtn').addEventListener('click', function () {
            // Fetch camera mode status
            fetch('/get_camera_status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('dayStatus').textContent = `${data.day_mode_count} cameras`;
                    document.getElementById('nightStatus').textContent = `${data.night_mode_count} cameras`;
                })
                .catch(error => console.error('Error refreshing camera status:', error));

            // Fetch the latest time profile status
            fetch('/get_time_profile')
                .then(response => response.json())
                .then(data => {
                    const timeProfileStatus = document.getElementById('timeProfileStatus');
                    timeProfileStatus.textContent = `Day Time: ${data.day_time} | Night Time: ${data.night_time}`;
                })
                .catch(error => console.error('Error refreshing time profile status:', error));
        });

        document.getElementById('addCameraBtn').addEventListener('click', function() {
            const ip = document.getElementById('camera_ip').value;
            fetch('/add_camera', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `ip=${ip}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    alert(data.message);
                } else {
                    alert(`Error: ${data.message}`);
                }
            });
        });

        window.onload = function() {
            fetch('/get_time_profile')
                .then(response => response.json())
                .then(data => {
                    const statusDiv = document.getElementById('timeProfileStatus');
                    statusDiv.textContent = `Day Time: ${data.day_time} | Night Time: ${data.night_time}`;
                })
                .catch(error => console.error('Error fetching time profile:', error));
        };