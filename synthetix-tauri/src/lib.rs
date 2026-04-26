#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            // Check for updates on startup
            check_for_update(app.handle().clone());
            if let Err(e) = start_backend(app.handle().clone()) {
                eprintln!("[backend] sidecar not available: {} (run 'python main.py' manually)", e);
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn start_backend(app_handle: tauri::AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    use tauri_plugin_shell::ShellExt;
    use tauri_plugin_shell::process::CommandEvent;

    let (rx, _child) = app_handle.shell().sidecar("binaries/backend")?.spawn()?;

    tauri::async_runtime::spawn(async move {
        let mut rx = rx;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("[backend] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[backend:err] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Terminated(status) => {
                    eprintln!("[backend] exited with status: {:?}", status);
                    break;
                }
                CommandEvent::Error(err) => {
                    eprintln!("[backend:error] {}", err);
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

fn check_for_update(app_handle: tauri::AppHandle) {
    tauri::async_runtime::spawn(async move {
        use tauri::Emitter;
        use tauri_plugin_updater::UpdaterExt;

        let updater = match app_handle.updater() {
            Ok(u) => u,
            Err(_) => return, // updater not configured, skip silently
        };

        match updater.check().await {
            Ok(Some(update)) => {
                println!(
                    "[updater] 新版本可用: {} (当前: {})",
                    update.version, update.current_version
                );
                let body = update.body.unwrap_or_else(|| "".to_string());
                let _ = app_handle.emit("update-available", body);
            }
            Ok(None) => {
                println!("[updater] 已是最新版本");
            }
            Err(_) => {
                // no remote release yet or network issue, skip silently
            }
        }
    });
}
