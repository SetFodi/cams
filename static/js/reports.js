        async function loadCameras() {
            try {
                // Fetch all data from the backend
                const response = await fetch('/refresh_camera_status');
                const data = await response.json();

                // Destructure data for easier access
                const { cameras } = data;

                // Calculate statistics
                const totalCameras = cameras.length;
                const connectedCameras = cameras.filter(camera => camera.status === 'Connected').length;
                const notConnectedCameras = totalCameras - connectedCameras;

                // Update statistics section
                const cameraStats = `
                    Total Cameras: ${totalCameras} |
                    Connected: <span class="connected">${connectedCameras}</span> |
                    Not Connected: <span class="not-connected">${notConnectedCameras}</span>
                `;
                document.getElementById('cameraStats').innerHTML = cameraStats;

                // Update camera list section
                const cameraList = cameras
                    .map(camera => `
                        <div class="camera" id="camera-${camera.ip}">
                            <p>
                                ${camera.ip} -
                                <span class="status ${camera.status === 'Connected' ? 'connected' : 'not-connected'}">
                                    ${camera.status}
                                </span>
                            </p>
                            <button class="btn" onclick="removeCamera('${camera.ip}')">Remove</button>
                        </div>
                    `)
                    .join('');
                document.getElementById('cameraList').innerHTML = cameraList;
            } catch (error) {
                alert('Error loading cameras: ' + error);
            }
        }

        async function removeCamera(ip) {
            try {
                const response = await fetch(`/remove_camera/${ip}`, { method: 'POST' });
                const data = await response.json();
                if (data.status === "success") {
                    alert("Camera removed successfully!");
                    loadCameras(); // Reload the camera list
                } else {
                    alert(`Error: ${data.message}`);
                }
            } catch (error) {
                alert('Error removing camera: ' + error);
            }
        }

        // Load cameras when the page is ready
        document.addEventListener('DOMContentLoaded', loadCameras);
