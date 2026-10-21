import { Component } from 'react'

// Keeps a crash on one page from blanking out the whole app (nav, chat, etc.)
// React unmounts the entire tree on an uncaught render error without this.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Page crashed:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page">
          <div className="error">Something went wrong loading this page: {this.state.error.message}</div>
        </div>
      )
    }
    return this.props.children
  }
}
