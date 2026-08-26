import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [frappeui({ frontendRoute: '/sales' }), vue()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
})
