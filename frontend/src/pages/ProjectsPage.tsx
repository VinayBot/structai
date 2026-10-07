import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { chatsApi, projectsApi } from '../lib/api'
import type { Chat, Project } from '../lib/types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<Project | null>(null)
  const [chats, setChats] = useState<Chat[]>([])
  const [newProjectName, setNewProjectName] = useState('')
  const [newChatTitle, setNewChatTitle] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void refreshProjects()
  }, [])

  useEffect(() => {
    if (selected) void refreshChats(selected.id)
    else setChats([])
  }, [selected])

  async function refreshProjects() {
    setLoading(true)
    try {
      setProjects((await projectsApi.list()).items)
    } finally {
      setLoading(false)
    }
  }

  async function refreshChats(projectId: string) {
    setChats((await chatsApi.list(projectId)).items)
  }

  async function handleCreateProject(e: FormEvent) {
    e.preventDefault()
    if (!newProjectName.trim()) return
    const project = await projectsApi.create(newProjectName.trim())
    setNewProjectName('')
    setProjects((prev) => [...prev, project])
  }

  async function handleDeleteProject(project: Project) {
    await projectsApi.remove(project.id)
    setProjects((prev) => prev.filter((p) => p.id !== project.id))
    if (selected?.id === project.id) setSelected(null)
  }

  async function handleCreateChat(e: FormEvent) {
    e.preventDefault()
    if (!selected || !newChatTitle.trim()) return
    const chat = await chatsApi.create(newChatTitle.trim(), selected.id)
    setNewChatTitle('')
    setChats((prev) => [...prev, chat])
  }

  async function handleDeleteChat(chat: Chat) {
    await chatsApi.remove(chat.id)
    setChats((prev) => prev.filter((c) => c.id !== chat.id))
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section>
        <h1 className="mb-4 text-xl font-semibold text-text">Projects</h1>
        <form onSubmit={handleCreateProject} className="mb-4 flex gap-2">
          <Input
            placeholder="New project name"
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
          />
          <Button type="submit">Create</Button>
        </form>

        {loading ? (
          <p className="text-sm text-text-dim">Loading…</p>
        ) : projects.length === 0 ? (
          <p className="text-sm text-text-dim">No projects yet.</p>
        ) : (
          <ul className="space-y-2">
            {projects.map((project) => (
              <li key={project.id}>
                <Card
                  className={`flex cursor-pointer items-center justify-between ${
                    selected?.id === project.id ? 'border-accent' : ''
                  }`}
                  onClick={() => setSelected(project)}
                >
                  <span className="text-sm text-text">{project.name}</span>
                  <Button
                    variant="danger"
                    onClick={(e) => {
                      e.stopPropagation()
                      void handleDeleteProject(project)
                    }}
                  >
                    Delete
                  </Button>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold text-text">
          {selected ? `Chats in "${selected.name}"` : 'Select a project'}
        </h2>

        {selected && (
          <>
            <form onSubmit={handleCreateChat} className="mb-4 flex gap-2">
              <Input
                placeholder="New chat title"
                value={newChatTitle}
                onChange={(e) => setNewChatTitle(e.target.value)}
              />
              <Button type="submit">Create</Button>
            </form>

            {chats.length === 0 ? (
              <p className="text-sm text-text-dim">No chats in this project yet.</p>
            ) : (
              <ul className="space-y-2">
                {chats.map((chat) => (
                  <li key={chat.id}>
                    <Card className="flex items-center justify-between">
                      <Link to={`/app/chat?chatId=${chat.id}`} className="text-sm text-text hover:text-accent">
                        {chat.title}
                      </Link>
                      <Button variant="danger" onClick={() => void handleDeleteChat(chat)}>
                        Delete
                      </Button>
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  )
}
